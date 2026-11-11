import copy,json,unittest
import relay
class Tests(unittest.TestCase):
 def setUp(self):
  self.init,self.state=relay.begin();self.h,self.secret=relay.receive(self.init,'123','a'*40,now=100)
  self.env=relay.seal(self.state,self.h,'synthetic-private-key','private sky question','123','a'*40,now=100)
 def call(self,key,msg):
  self.assertEqual(key,'synthetic-private-key');self.assertEqual(msg,'private sky question')
  return {'status':'OK','assistant_text':'synthetic private answer','simulated':True}
 def response(self):return relay.execute(self.h,self.secret,self.env,self.call,now=101)
 def test_roundtrip(self):self.assertTrue(relay.collect(self.state,self.response())['result']['simulated'])
 def test_public_objects_have_no_plaintext(self):
  s=json.dumps([self.init,self.h,self.env,self.response()])
  for value in ['synthetic-private-key','private sky question','synthetic private answer',self.state['client_private'],self.secret]:self.assertNotIn(value,s)
 def test_response_tampering(self):
  r=self.response();r['box']['ciphertext']='A'+r['box']['ciphertext'][1:] if not r['box']['ciphertext'].startswith('A') else 'B'+r['box']['ciphertext'][1:]
  with self.assertRaises(Exception):relay.collect(self.state,r)
 def test_request_tampering(self):
  e=copy.deepcopy(self.env);e['box']['nonce']=relay.enc(b'0'*12)
  with self.assertRaises(Exception):relay.execute(self.h,self.secret,e,self.call,now=101)
 def test_wrong_run(self):
  _,s=relay.begin()
  with self.assertRaises(ValueError):relay.seal(s,self.h,'synthetic-private-key','hi','wrong','a'*40,now=100)
 def test_expiry(self):
  with self.assertRaises(ValueError):relay.execute(self.h,self.secret,self.env,self.call,now=701)
 def test_double_collection(self):
  r=self.response();relay.collect(self.state,r)
  with self.assertRaises(ValueError):relay.collect(self.state,r)
 def test_double_seal(self):
  with self.assertRaises(ValueError):relay.seal(self.state,self.h,'synthetic-private-key','hi','123','a'*40,now=100)
 def test_wrong_client(self):
  _,s=relay.begin();s.update(sealed=True,handshake=self.h,envelope_sha256=relay.digest(self.env))
  with self.assertRaises(Exception):relay.collect(s,self.response())
if __name__=='__main__':unittest.main()
