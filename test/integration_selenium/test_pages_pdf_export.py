from .framework import (
    selenium_test,
    SeleniumIntegrationTestCase,
)


class TestPagesPdfExportSeleniumIntegration(SeleniumIntegrationTestCase):
    ensure_registered = True

    @classmethod
    def handle_galaxy_config_kwds(cls, config):
        super().handle_galaxy_config_kwds(config)
        config["enable_beta_markdown_export"] = True

    @selenium_test
    def test_page_pdf_export(self):
        self.navigate_to_pages()
        self.screenshot("pages_grid")
        self.create_page()
        self.components.pages.drop.wait_for_and_click()
        self.sleep_for(self.wait_types.UX_RENDER)
        self.components.pages.drop_edit.wait_for_and_click()
        self.components.pages.editor.markdown_editor.wait_for_and_send_keys("moo\n\n\ncow\n\n")
        self.screenshot("pages_markdown_editor")
        self.sleep_for(self.wait_types.UX_RENDER)
        self.screenshot("pages_markdown_editor_content")
        self.components.pages.editor.save.wait_for_and_click()
        self.screenshot("pages_markdown_editor_saved")
        self.sleep_for(self.wait_types.UX_RENDER)
        self.navigate_to_pages()
        self.components.pages.drop.wait_for_and_click()
        self.sleep_for(self.wait_types.UX_RENDER)
        self.components.pages.drop_view.wait_for_and_click()
        self.screenshot("pages_view_simple")
        self.components.pages.export.wait_for_and_click()
        self.sleep_for(self.wait_types.UX_RENDER)
