import {createServer} from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
const args=process.argv.slice(2);
if(args.includes('--help')){console.log('node vico_web/tools/serve.mjs --root DIST --port 4173 (localhost only)');process.exit(0);}
const get=k=>args[args.indexOf(k)+1];if(!args.includes('--root'))throw new Error('--root required');
const root=await fs.realpath(path.resolve(get('--root'))),port=args.includes('--port')?Number(get('--port')):4173;
if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid port');
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json','.wav':'audio/wav'};
const server=createServer(async(req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Cache-Control','no-cache');
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
  try{
    let name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(name.endsWith('/'))name+='index.html';
    if(name.includes('\\')||name.split('/').some(x=>x==='..'||x.startsWith('.')))throw new Error('Invalid path');
    const file=await fs.realpath(path.join(root,name));if(!file.startsWith(root+path.sep))throw new Error('Outside root');
    const bytes=await fs.readFile(file);res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Content-Length':bytes.length});res.end(req.method==='HEAD'?undefined:bytes);
  }catch{res.writeHead(404);res.end('Not found');}
});
server.listen(port,'127.0.0.1',()=>console.log(`Vico Web: http://localhost:${port} (development only)`));
