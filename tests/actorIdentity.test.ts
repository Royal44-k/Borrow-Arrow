import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {resolveActor,actorVisibleInMode,ACTOR_ASSETS} from '../src/actor-identity.ts';

test('approved network speakers have actual portrait assets; camera directions do not',()=>{
 const network=JSON.parse(readFileSync(new URL('../content/caocuan/s11/network.json',import.meta.url),'utf8'));
 for(const node of Object.values(network.nodes) as Array<{speaker:string}>){if(['镜头','末场','旁白'].includes(node.speaker)){assert.equal(resolveActor(node.speaker),null);}else assert.ok(resolveActor(node.speaker),`missing speaker: ${node.speaker}`);}
});
test('boatman aliases and shore reports resolve to the established support actors',()=>{
 for(const speaker of ['韩伯','船夫','老船夫','船工','船夫 · 韩伯','韩伯（低声）'])assert.equal(resolveActor(speaker)?.id,'hanbo',speaker);
 for(const speaker of ['哨长','岸上军士','岸上弓手','曹军哨长'])assert.equal(resolveActor(speaker)?.id,'watchman',speaker);
 assert.equal(resolveActor('阿成')?.frame,1);assert.equal(resolveActor('周都督')?.id,'zhouyu');
});
test('principal aliases preserve one identity and the correct atlas columns',()=>{
 for(const speaker of ['诸葛亮','孔明','诸葛孔明'])assert.equal(resolveActor(speaker)?.id,'zhuge');
 assert.equal(resolveActor('鲁肃')?.frame,0);assert.equal(resolveActor('孔明')?.frame,1);assert.equal(resolveActor('曹操')?.frame,2);
 assert.equal(resolveActor('子敬')?.id,'lusu');assert.equal(resolveActor('曹丞相')?.id,'cao');
});
test('army names, scene descriptions and unknown names never become Cao Cao or a fabricated fallback',()=>{
 for(const name of ['曹军','曹营','曹军已停射','曹姓船夫','诸葛亮与鲁肃','镜头','旁白','导演','末场','','未知人物'])assert.equal(resolveActor(name),null,name);
});
test('object and return operations suppress portraits while story mode remains available',()=>{
 for(const mode of ['drum','helm','collect','fire','return'])assert.equal(actorVisibleInMode(mode),false,mode);
 assert.equal(actorVisibleInMode('story'),true);assert.equal(actorVisibleInMode(undefined),true);
});
test('every declared atlas exists with the inspected dimensions and supports valid source columns',()=>{
 for(const asset of Object.values(ACTOR_ASSETS)){const path=new URL('../src/assets/'+asset.file,import.meta.url);assert.ok(existsSync(path));if(asset.columns>1){const bytes=readFileSync(path);assert.equal(bytes.readUInt32BE(16),asset.width);assert.equal(bytes.readUInt32BE(20),asset.height);}}
 for(const speaker of ['韩伯','阿成','周瑜','哨长','鲁肃','孔明','曹操','沈砚']){const actor=resolveActor(speaker)!;assert.ok(actor.frame>=0&&actor.frame<ACTOR_ASSETS[actor.atlas].columns);}
});
