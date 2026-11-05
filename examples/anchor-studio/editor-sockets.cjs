/* One authenticated upgrade dispatcher preserves Node-RED's own websocket
 * handlers. The editor channel transports heartbeats only, never execution. */
'use strict';
function attachEditorSockets({server,redServer,access,WebSocketServer,editorEnabled}){
 if(!server||!redServer||typeof access?.upgrade!=='function'||typeof WebSocketServer!=='function'||typeof editorEnabled!=='function')throw Error('TRUSTED_SOCKET_HOST_REQUIRED');
 const pushes=new WebSocketServer({noServer:true,maxPayload:65536});
 function upgrade(req,socket,head){
  access.upgrade(req,socket);
  if(socket.destroyed)return;
  if(!editorEnabled()||req.url.split('?')[0]!=='/rest/push')return redServer.emit('upgrade',req,socket,head);
  if(pushes.clients.size>=8)return socket.destroy();
  pushes.handleUpgrade(req,socket,head,ws=>{
   ws.on('error',()=>{});
   ws.on('message',bytes=>{
    try{const value=JSON.parse(bytes.toString('utf8'));if(value?.type!=='heartbeat')ws.close(1008,'Unsupported editor message');}
    catch{ws.close(1008,'Invalid editor message');}
   });
  });
 }
 server.on('upgrade',upgrade);
 return Object.freeze({close(){server.off('upgrade',upgrade);for(const ws of pushes.clients)ws.terminate();pushes.close();}});
}
module.exports={attachEditorSockets};
