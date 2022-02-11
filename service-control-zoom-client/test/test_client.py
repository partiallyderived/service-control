import unittest.mock as mock
from unittest.mock import Mock

import pytest

from servicecontrol.tools.data import DataDict
from servicecontrol.zoom.client import ZoomClientService


@pytest.fixture
def data() -> DataDict:
    # DataDict to use for test initialization.
    return DataDict(Mock())


def test_zoom_client(data: DataDict) -> None:
    # Test the Zoom client.

    config = {
        'id': 'Zoom ID',
        'refresh': 'Zoom Refresh Token',
        'secret': 'Zoom Secret'
    }
    with mock.patch('servicecontrol.zoom.client.Session', autospec=True) as mock_session_type:
        client = ZoomClientService(config, data)
        client.name = client.NAME
        assert client._auth == ('Zoom ID', 'Zoom Secret')
        assert client._refresh_token == 'Zoom Refresh Token'
        assert not client.installed()
        client.install()
        assert client.installed()
        assert client._data[client.name] == {'refresh': 'Zoom Refresh Token'}

        mock_session = mock_session_type.return_value
        mock_post = mock_session.post
        mock_post_response = mock_post.return_value
        mock_post_json = mock_post_response.json
        mock_post_json.return_value = {
            'access_token': 'Zoom Token',
            'expires_in': 3500,
            'refresh_token': 'New Refresh Token'
        }

        # Mock time.time so we can see how client behaves with regards to when the token refreshes.
        with mock.patch('time.time') as mock_time:
            mock_time.return_value = 1000
            client._refresh()
            assert client._refresh_token == 'New Refresh Token'  # Should have gotten new one.

            mock_post.assert_called_with(
                ZoomClientService.TOKEN_URL,
                auth=client._auth,
                params={'grant_type': 'refresh_token', 'refresh_token': 'Zoom Refresh Token'},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            assert client._token == 'Zoom Token'
            assert client._expire_time == 1000 + 3500 - 60
            mock_post_response.raise_for_status.assert_called()
            mock_post_response.reset_mock()

            mock_time.reset_mock()
            mock_time.return_value = 1500
            mock_post_response.json.return_value = {
                'access_token': 'Other Token', 'expires_in': 2500, 'refresh_token': 'Newer Refresh Token'
            }
            mock_get = mock_session.get
            mock_get_response = mock_get.return_value
            resp = client.get('users', arbitrary=5, also_arbitrary='6')

            # New token should not have been requested.
            assert client._token == 'Zoom Token'
            assert client._expire_time == 1000 + 3500 - 60

            # Check that expected calls were there, including having authorization header added.
            mock_get = mock_session.get
            assert resp == mock_get_response
            mock_get_response.raise_for_status.assert_called()
            mock_get.assert_called_with(
                f'{ZoomClientService.BASE}/users',
                headers={'Authorization': f'Bearer {client._token}'},
                arbitrary=5,
                also_arbitrary='6'
            )
            mock_get.reset_mock()

            # Test that token is detected as being expired and that headers kwarg will be added to instead of
            # replaced.
            mock_time.return_value = 5000
            client.get('users', headers={'my-header': 'my-value'})
            assert client._token == 'Other Token'
            assert client._expire_time == 5000 + 2500 - 60
            assert client._refresh_token == 'Newer Refresh Token'
            mock_get.assert_called_with(
                f'{ZoomClientService.BASE}/users',
                headers={'my-header': 'my-value', 'Authorization': f'Bearer {client._token}'}
            )

            # Test that each verb works correctly.
            with mock.patch.object(client, '_send') as mock_send:
                for verb in ['delete', 'get', 'patch', 'post', 'put']:
                    method = getattr(client, verb)
                    method('path', kwarg1='val1', kwarg2='val2')
                    mock_send.assert_called_with(verb, 'path', kwarg1='val1', kwarg2='val2')
