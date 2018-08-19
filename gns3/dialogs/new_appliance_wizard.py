# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import tempfile
import json

from gns3.qt import QtCore, QtWidgets, qpartial
from gns3.controller import Controller
from gns3.appliance_manager import ApplianceManager
from gns3.dialogs.preferences_dialog import PreferencesDialog

from ..ui.new_appliance_wizard_ui import Ui_NewApplianceWizard

import logging
log = logging.getLogger(__name__)


class NewApplianceWizard(QtWidgets.QWizard, Ui_NewApplianceWizard):
    """
    New appliance wizard.
    """

    def __init__(self, parent):

        super().__init__(parent)
        self.setupUi(self)

        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        if sys.platform.startswith("darwin"):
            # we want to see the cancel button on OSX
            self.setOptions(QtWidgets.QWizard.NoDefaultButton)

        self.uiAddApplianceManuallyRadioButton.toggled.connect(self._addApplianceToggledSlot)
        self.uiAddApplianceFromTemplateFileRadioButton.toggled.connect(self._addApplianceToggledSlot)

        # add a custom button to show appliance information
        self.setButtonText(QtWidgets.QWizard.CustomButton1, "&Update from online registry")
        self.setOption(QtWidgets.QWizard.HaveCustomButton1, True)
        self.customButtonClicked.connect(self._downloadApplianceTemplatesSlot)
        self.button(QtWidgets.QWizard.CustomButton1).hide()

        self.uiFilterLineEdit.textChanged.connect(self._filterTextChangedSlot)
        ApplianceManager.instance().appliances_changed_signal.connect(self._get_appliance_templates_from_server)

    def _addApplianceToggledSlot(self, checked):

        if checked:
            self.button(QtWidgets.QWizard.FinishButton).setEnabled(True)
            self.button(QtWidgets.QWizard.NextButton).setEnabled(False)
        else:
            self.button(QtWidgets.QWizard.FinishButton).setEnabled(False)
            self.button(QtWidgets.QWizard.NextButton).setEnabled(True)

    def _downloadApplianceTemplatesSlot(self):
        """
        Request server to update appliance templates from online registry.
        """

        ApplianceManager.instance().refresh(update=True)

    def _filterTextChangedSlot(self, text):

        self._get_appliance_templates_from_server(appliance_filter=text)

    def _setItemIcon(self, item, icon):
            item.setIcon(0, icon)

    def _get_tooltip_text(self, appliance):
        """
        Gets the appliance information to be displayed in the tooltip.
        """

        info = (
            ("Product", "product_name"),
            ("Vendor", "vendor_name"),
            ("Availability", "availability"),
            ("Status", "status"),
            ("Maintainer", "maintainer"),
            ("vCPUs", "qemu/vcpus"),
            ("RAM", "qemu/ram"),
            ("Adapters", "qemu/adapters"),
            ("Adapter type", "qemu/adapter_type"),
            ("Console type", "qemu/console_type"),
            ("Architecture", "qemu/arch"),
            ("KVM", "qemu/kvm")
        )

        text_info = ""
        for (name, key) in info:
            if "/" in key:
                key, subkey = key.split("/")
                value = appliance.get(key, {}).get(subkey, None)
            else:
                value = appliance.get(key, None)
            if value is None:
                continue
            text_info += "<span style='font-weight:bold;'>{}</span>: {}<br>".format(name, value)

        return text_info

    def _get_appliance_templates_from_server(self, appliance_filter=None):
        """
        Gets the appliance templates from the server and display them.
        """

        self.uiApplianceTemplatesTreeWidget.clear()
        for appliance in ApplianceManager.instance().applianceTemplates():
            if appliance_filter is None:
                appliance_filter = self.uiFilterLineEdit.text().strip()
            if appliance_filter and appliance_filter.lower() not in appliance["name"].lower():
                continue

            item = QtWidgets.QTreeWidgetItem(self.uiApplianceTemplatesTreeWidget)
            if appliance["builtin"]:
                appliance_name = appliance["name"]
            else:
                appliance_name = "{} (custom)".format(appliance["name"])

            item.setText(0, appliance_name)
            item.setText(1, appliance["category"].capitalize().replace("_", " "))

            if "qemu" in appliance:
                item.setText(2, "Qemu")
            elif "iou" in appliance:
                item.setText(2, "IOU")
            elif "dynamips" in appliance:
                item.setText(2, "Dynamips")
            elif "docker" in appliance:
                item.setText(2, "Docker")
            else:
                item.setText(2, "N/A")

            item.setText(3, appliance["vendor_name"])
            item.setData(0, QtCore.Qt.UserRole, appliance)
            item.setSizeHint(0, QtCore.QSize(32, 32))
            item.setToolTip(0, self._get_tooltip_text(appliance))
            Controller.instance().getSymbolIcon(appliance.get("symbol"), qpartial(self._setItemIcon, item),
                                                fallback=":/symbols/" + appliance["category"] + ".svg")

        self.uiApplianceTemplatesTreeWidget.resizeColumnToContents(0)
        self.uiApplianceTemplatesTreeWidget.sortByColumn(0, QtCore.Qt.AscendingOrder)

    def initializePage(self, page_id):
        """
        Initialize Wizard pages.

        :param page_id: page identifier
        """

        super().initializePage(page_id)
        if self.page(page_id) == self.uiApplianceFromServerWizardPage:
            self.button(QtWidgets.QWizard.CustomButton1).show()
            self.setButtonText(QtWidgets.QWizard.FinishButton, "&Install")
            self._get_appliance_templates_from_server()
        else:
            self.button(QtWidgets.QWizard.CustomButton1).hide()

    def cleanupPage(self, page_id):
        """
        Restore button default settings on the first page.
        """

        self.button(QtWidgets.QWizard.CustomButton1).hide()
        self.setButtonText(QtWidgets.QWizard.FinishButton, "&Finish")
        super().cleanupPage(page_id)

    def validateCurrentPage(self):
        """
        Validates if an appliance can be installed.
        """

        if self.currentPage() == self.uiApplianceFromServerWizardPage:
            if not self.uiApplianceTemplatesTreeWidget.currentItem():
                QtWidgets.QMessageBox.critical(self, "Appliance", "Please select an appliance to install!")
                return False
        return True

    def done(self, result):
        """
        This dialog is closed.

        :param result: ignored
        """

        super().done(result)
        from gns3.main_window import MainWindow
        if self.currentPage() == self.uiApplianceFromServerWizardPage:
            item = self.uiApplianceTemplatesTreeWidget.currentItem()
            if item:
                f = tempfile.NamedTemporaryFile(mode="w+", suffix=".builtin.gns3a", delete=False)
                json.dump(item.data(0, QtCore.Qt.UserRole), f)
                f.close()
                MainWindow.instance().loadPath(f.name)
        elif self.uiAddApplianceManuallyRadioButton.isChecked():
            dialog = PreferencesDialog(self.parent())
            dialog.exec_()
        elif self.uiAddApplianceFromTemplateFileRadioButton.isChecked():
            from gns3.main_window import MainWindow
            MainWindow.instance().openApplianceActionSlot()
