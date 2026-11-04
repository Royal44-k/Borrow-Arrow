import test from 'node:test'
import assert from 'node:assert/strict'
import {fleetSlots,riverPoint,riverFeedback} from '../src/v13/riverNavigation.ts'
import {warDrumSamples,WAR_DRUM_MODES} from '../src/v13/drumSynthesis.ts'
test('route placement clamps to existing river and exposes both sides of each boundary',()=>{assert.deepEqual(riverPoint(100,-90),{x:9,z:-12});assert.equal(riverFeedback('position',0,-9).safe,false);assert.equal(riverFeedback('position',0,2).safe,true);assert.equal(riverFeedback('command',0,5).safe,false);assert.equal(riverFeedback('command',0,-8).safe,true);assert.equal(riverFeedback('rescue',5,4).safe,true);assert.equal(riverFeedback('rescue',-4,4).safe,false)})
test('twenty boats retain distinct slots with central leader and free starboard retreat lane',()=>{const slots=fleetSlots();assert.equal(slots.length,20);assert.deepEqual(slots[0],{x:0,z:0});assert.equal(new Set(slots.map(p=>`${p.x},${p.z}`)).size,20);assert.ok(slots.every(p=>p.x<7));assert.ok(Math.abs(Math.max(...slots.map(p=>p.z))-12.6)<1e-9)})
test('war drum has stable low membrane modes, deterministic transient and bounded decaying tail',()=>{assert.equal(WAR_DRUM_MODES[0].hz,57);assert.ok(WAR_DRUM_MODES.every(m=>m.hz<250));const a=warDrumSamples(24000),b=warDrumSamples(24000);assert.deepEqual(a,b);assert.ok(a.every(v=>Number.isFinite(v)&&Math.abs(v)<=.821));const rms=(from:number,to:number)=>Math.sqrt(a.slice(from*24000,to*24000).reduce((s,v)=>s+v*v,0)/((to-from)*24000));assert.ok(rms(0,.3)>.2);assert.ok(rms(2.5,2.8)<rms(0,.3)*.15)})

