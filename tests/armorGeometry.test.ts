import test from 'node:test';
import assert from 'node:assert/strict';
import { createArmorDecoys } from '../src/armorGeometry.ts';
import { strawLayout } from '../src/boatGeometry.ts';

test('armor has one empty shell per authorized decoy position, with inspectable surfaces', () => {
  const layout=strawLayout(); const group=createArmorDecoys(layout);
  assert.equal(group.children.length,layout.length);
  group.children.forEach((shell,i)=>{
    assert.equal(shell.position.x,layout[i].x);
    assert.equal(shell.position.z,layout[i].z);
    assert.ok(shell.children.length>8);
    assert.ok(shell.children.every(part=>part.userData.part==='armor'));
  });
});
