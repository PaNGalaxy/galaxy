from .framework import (
    managed_history,
    selenium_test,
    SeleniumTestCase,
)


class PagesTestCase(SeleniumTestCase):

    ensure_registered = True

    @selenium_test
    @managed_history
    def test_simple_page_creation_edit_and_view(self):
        # Upload a file to test embedded object stuff
        test_path = self.get_filename("1.fasta")
        self.perform_upload(test_path)
        self.history_panel_wait_for_hid_ok(1)
        self.navigate_to_pages()
        self.screenshot("pages_grid")

        self.components.pages.create.wait_for_and_click()
        name = self._get_random_name(prefix="page")
        slug = self._get_random_name(prefix="pageslug")
        self.tool_set_value("title", name)
        self.tool_set_value("slug", slug)
        self.tool_set_value("content_format", "HTML", expected_type="select")
        self.screenshot("pages_create_form")

        # Sometimes 'submit' button not yet hooked up?
        self.sleep_for(self.wait_types.UX_RENDER)

        self.components.pages.submit.wait_for_and_click()

        self.click_grid_popup_option(name, "Edit content")
        self.components.pages.editor.wym_iframe.wait_for_visible()
        self.screenshot("pages_editor_new")
        self.driver.switch_to.frame(0)
        try:
            self.components.pages.editor.wym_iframe_content.wait_for_and_send_keys("moo\n\n\ncow\n\n")
        finally:
            self.driver.switch_to.default_content()

        self.components.pages.editor.embed_button.wait_for_and_click()
        self.screenshot("pages_editor_embed_menu")
        self.components.pages.editor.embed_dataset.wait_for_and_click()
        saved_datasets_element = self.components.pages.editor.dataset_selector.wait_for_and_click()
        self.screenshot("pages_editor_embed_dataset_dialog")
        checkboxes = saved_datasets_element.find_elements_by_css_selector("input[type='checkbox']")
        assert len(checkboxes) > 0
        checkboxes[0].click()
        self.components.pages.editor.embed_dialog_add_button.wait_for_and_click()

        self.sleep_for(self.wait_types.UX_RENDER)
        self.components.pages.editor.save.wait_for_and_click()
        self.screenshot("pages_editor_saved")
        self.home()
        self.navigate_to_pages()
        self.click_grid_popup_option(name, "View")
        self.screenshot("pages_view_simple")

    def navigate_to_pages(self):
        self.click_masthead_user()  # Open masthead menu
        self.components.masthead.pages.wait_for_and_click()
