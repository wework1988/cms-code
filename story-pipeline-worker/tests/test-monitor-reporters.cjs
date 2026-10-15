const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),os=require('os');
const root=path.resolve(__dirname,'../..');
for (const file of ['flow-image-agent/run-images.mjs','playright-automation/run-digen.js']) {
 const source=fs.readFileSync(path.join(root,file),'utf8');
 const code=source.slice(source.indexOf('// Read-only monitoring:'),source.indexOf('const __dirname'));
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'monitor-test-'));
 const target=path.join(tmp,'runner-status.json');
 const sandbox={fs,path,process:{pid:123,on(){}},setInterval:()=>({unref(){}}),clearInterval(){}};
 vm.createContext(sandbox);vm.runInContext(code,sandbox);
 sandbox.target=target;
 vm.runInContext('monitorStart(target); monitorWrite("downloading", 7);',sandbox);
 let record=JSON.parse(fs.readFileSync(target));
 assert.equal(record.scenes['7'].state,'downloading');assert(record.heartbeat_at>0);
 vm.runInContext('monitorPage = {context(){throw new Error("closed")}}; monitorWrite();',sandbox);
 record=JSON.parse(fs.readFileSync(target));assert.equal(record.browser,'unknown');assert.equal(record.state,'downloading');
 vm.runInContext('monitorPage = {context(){return {browser(){return {isConnected(){return false}}}}},isClosed(){return false}}; monitorWrite();',sandbox);
 assert.equal(JSON.parse(fs.readFileSync(target)).browser,'disconnected');
 fs.rmSync(tmp,{recursive:true});console.log(file+': reporter checks passed');
}
