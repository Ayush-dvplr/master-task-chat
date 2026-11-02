import sys, importlib.util
sys.path.insert(0, sys.argv[2])
spec = importlib.util.spec_from_file_location("t", sys.argv[1] + "/tests/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
shipped = open(sys.argv[1] + "/environment/repo/tests/test_visible.py").read()
cls = [l.split()[1].split("(")[0] for l in shipped.splitlines() if l.startswith("class ")][0]
cases = {
 "unchanged": shipped,
 "setUpModule raise SkipTest": shipped + "\n\ndef setUpModule():\n    raise unittest.SkipTest('x')\n",
 "module assign unittest.skip(...)(Case)": shipped + f"\n\n{cls} = unittest.skip('x')({cls})\n",
 "module expr skip": shipped + f"\n\nunittest.skip('x')({cls})\n",
 "tearDownModule skip": shipped + "\n\ndef tearDownModule():\n    unittest.SkipTest\n",
 "agent new test with skipIf (must NOT fire)": shipped + "\n\nclass Extra(unittest.TestCase):\n    @unittest.skipIf(sys.platform == 'win32', 'posix')\n    def test_extra(self):\n        pass\n",
}
for name, text in cases.items():
    t._visible_texts = lambda text=text: (shipped, text)
    print(f"{name}: fires={t._visible_test_removed()}")
