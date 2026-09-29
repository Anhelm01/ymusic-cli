"""Automated test for browser-based token auto-capture flow."""

from unittest.mock import MagicMock, patch
from ymusic_cli.config import Config
from ymusic_cli.auth import run_browser_device_auth, copy_to_clipboard


def test_clipboard_copy():
    # Should not raise any unhandled exceptions
    ok = copy_to_clipboard("test_code_1234")
    assert isinstance(ok, bool)


def test_browser_device_auth_flow(tmp_path):
    # Set up dummy config targeting tmp_path
    cfg_file = tmp_path / "config.json"
    cfg = Config()

    mock_code = MagicMock()
    mock_code.user_code = "abcd-efgh"
    mock_code.device_code = "mock_dev_code_999"
    mock_code.verification_url = "https://ya.ru/device"
    mock_code.interval = 0.01
    mock_code.expires_in = 10

    mock_token = MagicMock()
    mock_token.access_token = "y0_mock_token_captured_successfully"

    with patch("ymusic_cli.auth.Client") as MockClient, \
         patch("ymusic_cli.auth.webbrowser.open") as mock_browser_open, \
         patch("ymusic_cli.config.get_default_config_file", return_value=cfg_file):

        client_instance = MockClient.return_value
        client_instance.request_device_code.return_value = mock_code

        # First poll returns None (pending), second returns token
        client_instance.poll_device_token.side_effect = [None, mock_token]

        # Mock test_client init for verification
        mock_me = MagicMock()
        mock_me.account.login = "test_user"
        mock_me.account.full_name = "Test User"
        mock_status = MagicMock()
        mock_status.plus.has_plus = True
        client_instance.me = mock_me
        client_instance.account_status.return_value = mock_status
        client_instance.init.return_value = client_instance

        success = run_browser_device_auth(cfg, auto_exit=False)

        assert success is True
        assert cfg.token == "y0_mock_token_captured_successfully"
        assert mock_browser_open.called
        assert mock_browser_open.call_args[0][0] == "https://ya.ru/device"


if __name__ == "__main__":
    test_clipboard_copy()
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        test_browser_device_auth_flow(Path(td))
    print("ALL TOKEN AUTO-CAPTURE TESTS PASSED SUCCESSFULLY!")
