import test from 'node:test';
import assert from 'node:assert/strict';
import { placementsFor, sideForHeading, collectionBundles, takeBundle, fleetHeading, representativeBundleId, stageCommand, stageVisibility, arrowBatchPhase, encodeBundleTransfer, resolveBundleTransfer, pointerDroppedInBasket, scoutPosition, hotspotInSafeArea, stageShot, helmFromDrag, collectionDisplayPositions, shotProgress } from '../src/sceneGeometry.ts';

test('one-side arrangement always puts material on the actual right gunwale', () => {
  const points = placementsFor('right');
  assert.equal(points.length, 8);
  assert.ok(points.every(p => p.side === 'right' && p.z > 1));
  assert.ok(placementsFor('both').some(p => p.side === 'left' && p.z < -1));
  assert.equal(placementsFor('none').length, 0);
});
test('camera-independent heading keeps the original side at zero and turns the left at 180', () => {
  assert.equal(sideForHeading(0), 'right');
  assert.equal(sideForHeading(360), 'right');
  assert.equal(sideForHeading(180), 'left');
  assert.equal(sideForHeading(-180), 'left');
});
test('representative bundles only exist where this route actually retained arrows', () => {
  assert.deepEqual(collectionBundles('straw','both',0,0), []);
  const one = collectionBundles('straw','right',52000,51000);
  assert.equal(one.length, 3); assert.ok(one.every(p => p.side === 'right'));
  assert.equal(collectionBundles('armor','both',34000,0).length, 3);
  assert.deepEqual(collectionBundles('none','both',52000,0), []);
});
test('taking a bundle twice cannot count it twice or invent another bundle', () => {
  const bundles = collectionBundles('straw','both',52000,51000);
  const first = takeBundle(bundles, [], bundles[0]!.id);
  assert.equal(first.accepted,true); assert.equal(first.collected.length,1);
  assert.equal(takeBundle(bundles,first.collected,bundles[0]!.id).accepted,false);
  assert.equal(takeBundle(bundles,first.collected,'missing').accepted,false);
  let collected:string[]=[];
  for (const b of bundles) collected=takeBundle(bundles,collected,b.id).collected;
  assert.equal(takeBundle(bundles,collected,bundles[0]!.id).complete,true);
});
test('a command turns each boat in sequence and finite progress settles the fleet', () => {
  assert.equal(fleetHeading(0,180,0,0),0);
  assert.equal(fleetHeading(0,180,1,0),180);
  assert.equal(fleetHeading(0,180,.3,19),0);
  assert.equal(fleetHeading(0,180,1,19),180);
});

test('a representative bundle owns all neighboring arrow positions, leaving none on the cleared side', () => {
  const ids = Array.from({length:8},(_,i)=>representativeBundleId('right',i));
  assert.equal(new Set(ids).size,3);
  assert.ok(ids.every(id=>['right-1','right-3','right-6'].includes(id)));
});


test('return command cannot be mistaken for a side-changing helm command',()=>{
 assert.equal(stageCommand('return'),'return-confirm');
 assert.equal(stageCommand('helm'),'helm-confirm');
 assert.equal(stageCommand('inspect'),null);
});
test('shore perspective hides all ship details and preserves the no-contact river',()=>{
 assert.deepEqual(stageVisibility('shore',false),{showFleet:false,shipDetails:false,allowZoom:false});
 assert.deepEqual(stageVisibility('shore',true),{showFleet:true,shipDetails:false,allowZoom:false});
 assert.deepEqual(stageVisibility('ship',false),{showFleet:true,shipDetails:true,allowZoom:true});
});


test('second volley waits for the completed heading and only settles after its finite flight',()=>{
 assert.equal(arrowBatchPhase(0,180,5,null),'turning');
 assert.equal(arrowBatchPhase(90,180,5,null),'turning');
 assert.equal(arrowBatchPhase(180,180,5,null),'ready');
 assert.equal(arrowBatchPhase(180,180,5,5),'flying');
 assert.equal(arrowBatchPhase(180,180,7,5),'flying');
 assert.equal(arrowBatchPhase(180,180,8,5),'settled');
});


test('drag payload and click selection resolve to the same unique source bundle',()=>{
 const source=collectionBundles('straw','both',52000,51000),id=source[0]!.id;
 const payload=encodeBundleTransfer(id);
 assert.equal(resolveBundleTransfer(payload,'',source,[]),id);
 assert.equal(resolveBundleTransfer('',id,source,[]),id);
 const dropped=takeBundle(source,[],resolveBundleTransfer(payload,'',source,[]));
 assert.deepEqual(dropped,takeBundle(source,[],id));
 assert.equal(resolveBundleTransfer(payload,id,source,dropped.collected),'');
 assert.equal(resolveBundleTransfer('foreign text',id,source,[]),'');
 assert.equal(resolveBundleTransfer('caocuan-arrow:missing','',source,[]),'');
});


test('captured pointer release uses viewport basket bounds and requires an actual drag',()=>{
 const basket={left:825,right:1005,top:338,bottom:493};
 assert.equal(pointerDroppedInBasket({x:402,y:266},{x:915,y:416},basket),true);
 assert.equal(pointerDroppedInBasket({x:402,y:266},{x:402,y:266},basket),false);
 assert.equal(pointerDroppedInBasket({x:402,y:266},{x:800,y:416},basket),false);
 assert.equal(pointerDroppedInBasket({x:402,y:266},{x:915,y:416},undefined),false);
});


test('scout approaches from the shore once and stops safely beyond the learner boat',()=>{
 assert.deepEqual(scoutPosition(0),[8,-.1,28]);
 assert.deepEqual(scoutPosition(1),[8,-.1,17]);
 assert.deepEqual(scoutPosition(10),scoutPosition(1));
 assert.deepEqual(scoutPosition(-1),scoutPosition(0));
 for(let p=0;p<=1;p+=.1)assert.ok(scoutPosition(p)[2]>=17);
});


test('observation hotspots avoid header, dialogue, and title while operation targets remain reachable',()=>{
 assert.equal(hotspotInSafeArea('river',28,123,720),false);
 assert.equal(hotspotInSafeArea('inspect',500,89,720),false);
 assert.equal(hotspotInSafeArea('river',500,571,720),false);
 assert.equal(hotspotInSafeArea('river',500,250,720),true);
 assert.equal(hotspotInSafeArea('inspect',360,123,720),true);
 assert.equal(hotspotInSafeArea('collect',28,123,720),true);
 assert.equal(hotspotInSafeArea('place',500,89,720),true);
});



test('operation shots focus their objects and the consequence shot widens without orbiting the learner',()=>{
 const drum=stageShot('drum','ship',false),helm=stageShot('helm','ship',false),moving=stageShot('helm','ship',true);
 assert.equal(drum.kind,'object'); assert.equal(helm.kind,'object'); assert.equal(moving.kind,'fleet');
 assert.ok(drum.position[1]<3); assert.ok(moving.position[1]>helm.position[1]);
 assert.deepEqual(stageShot('river','shore',false),stageShot('drum','shore',false));
 assert.equal(stageShot('collect','ship',false).kind,'collection');
 assert.ok(stageShot('river','ship',false).position[1]<5);
});
test('dragging the tiller is bounded, reversible and preserves the committed starting heading',()=>{
 assert.equal(helmFromDrag(0,100,100,300),0); assert.equal(helmFromDrag(0,100,250,300),90);
 assert.equal(helmFromDrag(90,250,100,300),0); assert.equal(helmFromDrag(150,0,300,300),180);
 assert.equal(helmFromDrag(90,0,-300,300),0); assert.equal(helmFromDrag(90,0,1,0),90);
});
test('collection close-up preserves each real source bundle identity and never displays invented bundles',()=>{
 const source=collectionBundles('straw','both',52000,50000),display=collectionDisplayPositions(source);
 assert.deepEqual(display.map(p=>p.id),source.map(p=>p.id)); assert.equal(new Set(display.map(p=>p.x)).size,6);
 assert.deepEqual(collectionDisplayPositions([]),[]);
 assert.equal(collectionDisplayPositions(collectionBundles('straw','right',52000,0)).length,3);
});

test('camera transition uses elapsed time so a throttled frame still reaches the intended shot',()=>{assert.equal(shotProgress(10,10),0);assert.equal(shotProgress(12,10),1);assert.ok(Math.abs(shotProgress(10.525,10)-.5)<1e-9);assert.equal(shotProgress(9,10),0);});

