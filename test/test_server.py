import unittest
from easy_py_server import EasyPyServer, Method, Request
import requests


def mock_func():
    print("ok")


class TestEasyPyServer(unittest.TestCase):
    def test_reuse_address(self):
        self.assertTrue(EasyPyServer.allow_reuse_address)

    def test_add_listener(self):
        class Mock(object):
            def __init__(self):
                self.listeners_dic = {}

        mock = Mock()
        url = "/i"
        EasyPyServer.add_request_listener(mock, url, [Method.GET], mock_func)
        # print(mock.listeners_dic)
        self.assertTrue(len(mock.listeners_dic) == 1)
        self.assertTrue(mock.listeners_dic[url][0] == mock_func)


class FunctionalTest(unittest.TestCase):

    def setUp(self) -> None:
        self.server = None
        self.port = 8999
        self.addr = 'localhost'
        self.server = EasyPyServer(self.addr, port=self.port)

        def set(data, r: Request):
            r.set_session_attribute('data', data)
            return "ok"

        @self.server.get('/get')
        def get(r: Request):
            return r.get_session_attribute('data')

        self.server.add_request_listener('/set', [Method.GET], set)
        # fixme: debug 模式下会block 很奇怪
        self.thread = self.server.start_serve(blocking=False)

    def test_session(self):
        s = requests.Session()
        base_url = f'http://{self.addr}:{self.port}'
        rst = s.get(f'{base_url}/get')
        self.assertEqual(rst.headers['Content-Type'], 'application/octet-stream')
        self.assertEqual(len(rst.content), 0)
        rst = s.get(f'{base_url}/get')
        self.assertEqual(rst.headers['Content-Type'], 'application/octet-stream')
        self.assertEqual(len(rst.content), 0)
        test_data = "TEST"
        rst = s.get(f'{base_url}/set?data={test_data}')
        self.assertEqual(rst.text, 'ok')
        rst = s.get(f'{base_url}/get')
        self.assertIn('text/html', rst.headers['Content-Type'])
        self.assertEqual(rst.text, test_data)
        s.close()
        import sys
        print("session test success", file=sys.stderr)

    def tearDown(self) -> None:
        self.server.server_close()
        super().tearDown()


if __name__ == '__main__':
    unittest.main()
