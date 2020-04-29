import unittest
from easy_py_server import EasyPyServer, Method, Request
import requests
import multiprocessing as mt


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


class TestServerProcess(mt.Process):
    def run(self) -> None:
        addr, port = self._args
        server = EasyPyServer(addr, port=port)

        def set(data, r: Request):
            r.set_session_attribute('data', data)
            return "ok"

        @server.get('/get')
        def get(r: Request):
            return r.get_session_attribute('data')

        @server.get('/sum_2/:a/and/:bb')
        def sum_2(a: int, bb: int):
            return a + bb

        server.add_request_listener('/set', [Method.GET], set)
        server.run()


class FunctionalTest(unittest.TestCase):

    def setUp(self) -> None:
        if hasattr(self, 'server') and self.server is not None:
            return
        self.port = 8999
        self.addr = 'localhost'
        self.server = EasyPyServer(self.addr, port=self.port)

        def set(data, r: Request):
            r.set_session_attribute('data', data)
            return "ok"

        @self.server.get('/get')
        def get(r: Request):
            return r.get_session_attribute('data')

        @self.server.get('/sum_2/:a/and/:bb')
        def sum_2(a: int, bb: int):
            return a + bb

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
        print("\nsession test success")

    def test_path_param(self):
        base_url = f'http://{self.addr}:{self.port}'
        rst = requests.get(f'{base_url}/sum_2/7/and/2')
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, '9')
        rst = requests.get(f'{base_url}/sum_2/02/and/2/')
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, '4')
        rst = requests.get(f'{base_url}/sum_2/2/and/-3')
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, '-1')
        rst = requests.get(f'{base_url}/sum_2/-201/and/-3')
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, '-204')
        print("\npath_param test success")

    def tearDown(self) -> None:
        self.server.server_close()
        # self.process.kill()
        # self.process.join()
        pass


if __name__ == '__main__':
    unittest.main()
