import unittest
from easy_py_server import EasyPyServer, Method, Request, ResponseConfig
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
        EasyPyServer.add_request_listener(mock, url, [Method.GET, Method.OPTIONS], mock_func)
        # print(mock.listeners_dic)
        self.assertTrue(len(mock.listeners_dic) == 1)
        self.assertTrue(mock.listeners_dic[url][Method.GET][0] == mock_func)
        self.assertTrue(Method.POST not in mock.listeners_dic[url])
        self.assertTrue(mock.listeners_dic[url][Method.OPTIONS][0] == mock_func)


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

        @self.server.get('/sum_list')
        def sum_list_get(arr: list):
            return "get" + str(sum(arr))

        @self.server.post('/sum_list')
        def sum_list_post(arr: list):
            arr = [float(a) for a in arr]
            return "post" + str(sum(arr))

        # 自定义header
        @self.server.post("/cross", ResponseConfig(headers={'Access-Control-Allow-Origin': '*'}))
        def cross_access():
            return "post allow"

        self.server.add_request_listener('/set', [Method.GET], set)
        self.thread = self.server.start_serve(blocking=False)

    def test_static(self):
        base_url = f'http://{self.addr}:{self.port}'

        def test_file(url, expect_text, expect_content_type='text/html'):
            rst = requests.get(url)
            self.assertEqual(rst.status_code, 200)
            self.assertEqual(rst.headers['Content-Length'], str(len(rst.text)))
            self.assertEqual(rst.headers['Content-Type'], expect_content_type)
            self.assertEqual(rst.text, expect_text)

        def test_file_not_exist(url):
            rst = requests.get(url)
            self.assertEqual(rst.status_code, 404)
            self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
            self.assertTrue(len(rst.text) > 0)

        def test_forbidden(url):
            rst = requests.get(url)
            self.assertEqual(rst.status_code, 403)
            self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
            self.assertTrue(len(rst.text) > 0)

        test_file(f'{base_url}', '<!DOCTYPE html>test')
        test_file(f'{base_url}/', '<!DOCTYPE html>test')
        test_file(f'{base_url}/index.html', '<!DOCTYPE html>test')
        test_file(f'{base_url}?', '<!DOCTYPE html>test')
        test_file(f'{base_url}/?a=10', '<!DOCTYPE html>test')
        test_file(f'{base_url}?b=10', '<!DOCTYPE html>test')

        test_file(f'{base_url}/中文路径', '<!DOCTYPE html>test chinese')
        test_file(f'{base_url}/中文路径/index.html', '<!DOCTYPE html>test chinese')

        test_file(f'{base_url}/assets', '<!DOCTYPE html>test2')
        test_file(f'{base_url}/assets/', '<!DOCTYPE html>test2')
        test_file(f'{base_url}/assets/?', '<!DOCTYPE html>test2')
        test_file(f'{base_url}/assets/?a=10', '<!DOCTYPE html>test2')
        test_file(f'{base_url}/assets?b=10', '<!DOCTYPE html>test2')
        test_file(f'{base_url}/assets/index.html', '<!DOCTYPE html>test2')
        test_file(f'{base_url}/assets/index.html?', '<!DOCTYPE html>test2')
        test_file(f'{base_url}/assets/index.html?b=10', '<!DOCTYPE html>test2')

        test_file(f'{base_url}/assets/js/t-t.min.js', 'const test = 0', 'application/javascript')
        test_file(f'{base_url}/assets/js/t-t.min.js?a=10s', 'const test = 0', 'application/javascript')

        test_file_not_exist(f'{base_url}/assets/js/t-t.min.j')
        test_file_not_exist(f'{base_url}/a')
        test_file_not_exist(f'{base_url}/dad/adf')
        test_file_not_exist(f'{base_url}/ ')
        test_file_not_exist(f'{base_url}/中文路径 ')
        test_file_not_exist(f'{base_url}/ 中文路径')
        test_file_not_exist(f'{base_url}/中文路径/ ')

        test_forbidden(f'{base_url}/none')
        test_forbidden(f'{base_url}/assets/js/')
        test_forbidden(f'{base_url}/assets/js')
        test_forbidden(f'{base_url}/assets/js?a=12')

    def test_api(self):
        base_url = f'http://{self.addr}:{self.port}'
        rst = requests.get(f"{base_url}/sum_list?arr=[1.1, 2,3,4,5 ]")
        self.assertEqual(rst.status_code, 200)
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, 'get15.1')

        # post by request type: application/x-www-form-urlencoded
        rst = requests.post(f"{base_url}/sum_list", data=dict(arr=[1, 2, 3, 4, 5.2]))
        self.assertEqual(rst.status_code, 200)
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, 'post15.2')

        # post by request type: application/x-www-form-urlencoded
        rst = requests.post(f"{base_url}/sum_list", data=dict(arr=[1, 2, 3, 4, 5.5], none='nothing'))
        self.assertEqual(rst.status_code, 200)
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, 'post15.5')

        # post by request type: application/json
        rst = requests.post(f"{base_url}/sum_list", json=dict(arr=[1, 2.2, 3, 4], none='nothing'))
        self.assertEqual(rst.status_code, 200)
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.text, 'post10.2')

    def test_response_config(self):
        base_url = f'http://{self.addr}:{self.port}'
        rst = requests.post(f"{base_url}/cross")
        self.assertEqual(rst.status_code, 200)
        self.assertEqual(rst.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(rst.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(rst.text, 'post allow')

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
