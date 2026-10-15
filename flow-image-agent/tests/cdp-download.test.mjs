import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { receiveDownload } from '../cdp-download.mjs';

test('download belongs to correct tab and completes by matching GUID',async()=>{
  const session=new EventEmitter();
  const result=await receiveDownload({session,directory:'/tmp',frameId:'flow'},async()=>{
    session.emit('Browser.downloadWillBegin',{frameId:'other',guid:'wrong'});
    session.emit('Browser.downloadProgress',{guid:'wrong',state:'completed'});
    session.emit('Browser.downloadWillBegin',{frameId:'flow',guid:'correct'});
    session.emit('Browser.downloadProgress',{guid:'correct',state:'inProgress'});
    session.emit('Browser.downloadProgress',{guid:'correct',state:'completed'});
  },1000);
  assert.equal(result,'/tmp/correct');
  assert.equal(session.listenerCount('Browser.downloadProgress'),0);
});
test('canceled download is reported',async()=>{
  const session=new EventEmitter();
  await assert.rejects(receiveDownload({session,directory:'/tmp',frameId:'flow'},async()=>{
    session.emit('Browser.downloadWillBegin',{frameId:'flow',guid:'correct'});
    session.emit('Browser.downloadProgress',{guid:'correct',state:'canceled'});
  },1000),/canceled/);
});
test('Flow blob download is accepted when the frame id differs',async()=>{
  const session=new EventEmitter();
  const result=await receiveDownload({session,directory:'/tmp',frameId:'flow'},async()=>{
    session.emit('Browser.downloadWillBegin',{
      frameId:'other-frame',
      guid:'aeab6233-a432-42b6-82ec-9c1e6d6b1575',
      url:'blob:https://flow.google.com/7eee20bc-8cf8-4452-a842-64a9cb250676',
      suggestedFilename:'Guru_warns_king_in_underworld_2K_20261015164237.jpg',
    });
    session.emit('Browser.downloadProgress',{guid:'aeab6233-a432-42b6-82ec-9c1e6d6b1575',state:'completed'});
  },1000);
  assert.equal(result,'/tmp/aeab6233-a432-42b6-82ec-9c1e6d6b1575');
});
test('unrelated tab downloads are still ignored',async()=>{
  const session=new EventEmitter();
  await assert.rejects(receiveDownload({session,directory:'/tmp',frameId:'flow'},async()=>{
    session.emit('Browser.downloadWillBegin',{frameId:'gmail',guid:'mail-1',url:'https://mail.google.com/mail/u/0'});
    session.emit('Browser.downloadProgress',{guid:'mail-1',state:'completed'});
  },20),/timeout/);
});
test('no download times out and cleans listeners',async()=>{
  const session=new EventEmitter();
  await assert.rejects(receiveDownload({session,directory:'/tmp',frameId:'flow'},async()=>{},5),/timeout/);
  assert.equal(session.listenerCount('Browser.downloadWillBegin'),0);
});
