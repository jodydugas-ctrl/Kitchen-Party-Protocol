import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('worker',Path(__file__).with_name('worker.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class QueueTests(unittest.TestCase):
 def setUp(self):
  self.r={'schema':'kpp.openrouter-queue-request/1','request_id':'a'*32,'message':'Hello'};self.store={};self.calls=0
 def read(self,rid):return (self.store.get(rid),'sha' if rid in self.store else None)
 def write(self,rid,v,sha):self.store[rid]=v
 def call(self,key,msg):self.calls+=1;return {'status':'OK','assistant_text':'remote fixture'}
 def run_request(self,key='fixture-key'):m.process(self.r,'a'*32+'.json',self.read,self.write,self.call,key)
 def test_repeat_does_not_call_twice(self):
  self.run_request();self.run_request();self.assertEqual(self.calls,1)
 def test_crash_claim_is_not_retried(self):
  def crash(*a):raise RuntimeError()
  with self.assertRaises(RuntimeError):m.process(self.r,'a'*32+'.json',self.read,self.write,crash,'key')
  self.run_request();self.assertEqual(self.calls,0);self.assertEqual(self.store['a'*32]['status'],'CLAIMED_OUTCOME_UNKNOWN')
 def test_reused_id_rejected(self):
  self.run_request();self.r['message']='changed'
  with self.assertRaises(ValueError):self.run_request()
 def test_no_key_no_inference(self):
  self.run_request('');self.assertEqual(self.calls,0);self.assertEqual(self.store['a'*32]['status'],'SETUP_REQUIRED')
 def test_invalid_request_rejected(self):
  self.r['model']='paid'
  with self.assertRaises(ValueError):self.run_request()
if __name__=='__main__':unittest.main()
