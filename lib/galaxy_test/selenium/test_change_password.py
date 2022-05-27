from .framework import (
    selenium_test,
    SeleniumTestCase
)


class ChangePasswordTestCase(SeleniumTestCase):
    @selenium_test
    def test_change_password(self):
        self.home()
        email = self._get_random_email()
        self.register(email)
        self.click_masthead_user()
        self.components.masthead.preferences.wait_for_and_click()
        self.components.preferences.change_password.wait_for_and_click()
        new_password = self._get_random_password()
        self.fill_input_fields(self.default_password, new_password, new_password)
        self.logout_if_needed()
        self.submit_login(email, new_password)

    @selenium_test
    def test_new_password_password(self):
        self.register_and_change_password()
        self.fill_input_fields(self.default_password, "", self._get_random_password())
        self.assert_error_message(contains='Please provide a new password.')

    @selenium_test
    def test_no_password_confirmation(self):
        self.register_and_change_password()
        password = self._get_random_password()
        confirmation = self._get_random_password()
        self.fill_input_fields(self.default_password, password, confirmation)
        self.assert_error_message(contains='Passwords do not match.')

    @selenium_test
    def test_currect_password_incorrect(self):
        self.register_and_change_password()
        password = self._get_random_password()
        assert self.default_password != password
        self.fill_input_fields(password, password, password)
        self.assert_error_message(contains='Invalid current password.')

    @selenium_test
    def test_new_password_short(self):
        self.register_and_change_password()
        password = self._get_random_password(len=3)
        self.fill_input_fields(self.default_password, password, password)
        self.assert_error_message(contains='Use a password of at least 6 characters.')

    @selenium_test
    def test_new_password_same_password(self):
        self.register_and_change_password()
        password = self.default_password
        self.fill_input_fields(password, password, password)

    def register_and_change_password(self):
        self.home()
        self.register()
        self.click_masthead_user()
        self.components.masthead.preferences.wait_for_and_click()
        self.components.preferences.change_password.wait_for_and_click()

    def fill_input_fields(self, current, password, confirm):
        self.sleep_for(self.wait_types.UX_TRANSITION)
        self.driver.find_element_by_css_selector("input[id='current']").send_keys(current)
        self.driver.find_element_by_css_selector("input[id='password']").send_keys(password)
        self.driver.find_element_by_css_selector("input[id='confirm']").send_keys(confirm)
        self.components.change_user_password.submit.wait_for_and_click()
