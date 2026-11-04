import test from 'node:test';
import assert from 'node:assert/strict';
import { hullHalfWidth, hullPoint, arrowVisualCount, normalizeAngle, strawLayout } from '../src/boatGeometry.ts';

test('boat tapers at both ends, with a continuous broad midsection', () => {
  assert.ok(hullHalfWidth(0) > 1.2);
  assert.ok(hullHalfWidth(-4.8) < .15);
  assert.ok(hullHalfWidth(4.8) < .15);
  for (let x=-4.8;x<=4.8;x+=.2) assert.ok(Number.isFinite(hullHalfWidth(x)));
});

test('hull strakes meet at keel and mirror across the centreline', () => {
  for (const x of [-4.6,-2,0,2,4.6]) {
    const a=hullPoint(x,.8,1), b=hullPoint(x,.8,-1);
    assert.equal(a[0],b[0]); assert.equal(a[1],b[1]); assert.equal(a[2],-b[2]);
    assert.equal(hullPoint(x,0,1)[2],0);
    assert.ok(hullPoint(x,1,1)[1] > hullPoint(x,0,1)[1]);
  }
});

test('untrusted display density stays bounded and does not invent NaN geometry', () => {
  assert.equal(arrowVisualCount(-3),0);
  assert.equal(arrowVisualCount(Number.NaN),0);
  assert.equal(arrowVisualCount(0),0);
  assert.equal(arrowVisualCount(100),160);
  assert.equal(arrowVisualCount(9000),160);
});

test('angle normalization supports full rotations without discontinuous unbounded values', () => {
  assert.equal(normalizeAngle(-90),270);
  assert.equal(normalizeAngle(725),5);
  assert.equal(normalizeAngle(Number.POSITIVE_INFINITY),0);
});

test('straw layout leaves bow and stern clear and has symmetric paired working areas', () => {
  const parts=strawLayout(); assert.equal(parts.length,16);
  assert.equal(parts.filter(p=>p.side===1).length,8);
  assert.equal(parts.filter(p=>p.side===-1).length,8);
  assert.ok(parts.every(p=>Math.abs(p.x)<4.2 && Math.abs(p.z)<1.7));
});
