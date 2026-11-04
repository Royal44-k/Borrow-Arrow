import * as THREE from 'three';

/** Original stage prop, an empty lamellar shell on a timber support, not a historical reconstruction. */
export function createArmorDecoys(layout:Array<{x:number;z:number;side:number}>):THREE.Group {
  const group=new THREE.Group();
  const plate=new THREE.MeshStandardMaterial({color:'#4a514f',metalness:.52,roughness:.65,side:THREE.DoubleSide});
  const support=new THREE.MeshStandardMaterial({color:'#6a4930',roughness:.95});
  const binding=new THREE.MeshStandardMaterial({color:'#a68a5a',roughness:1});
  for(const p of layout){
    const shell=new THREE.Group(); shell.position.set(p.x,.38,p.z); shell.rotation.y=p.side<0?Math.PI:0;
    const add=(geo:THREE.BufferGeometry,mat:THREE.Material,x:number,y:number,z:number)=>{
      const mesh=new THREE.Mesh(geo,mat); mesh.position.set(x,y,z);mesh.userData.part='armor';mesh.castShadow=true;shell.add(mesh);return mesh;
    };
    add(new THREE.CylinderGeometry(.025,.035,1.22,6),support,0,.58,0);
    const bar=add(new THREE.CylinderGeometry(.025,.025,.68,6),support,0,.85,0);bar.rotation.z=Math.PI/2;
    for(let row=0;row<5;row++){
      const halfWidth=.19+row*.013;
      for(const facing of [-1,1]){
        const panel=add(new THREE.BoxGeometry(halfWidth*2,.125,.035),plate,0,.78-row*.125,facing*.11);
        panel.rotation.x=facing*-.09;
        for(const x of [-halfWidth*.7,halfWidth*.7]) add(new THREE.SphereGeometry(.014,5,4),binding,x,.79-row*.125,facing*.133);
      }
    }
    for(const side of [-1,1]){
      const shoulder=add(new THREE.BoxGeometry(.21,.04,.3),plate,side*.235,.9,0);shoulder.rotation.z=-side*.22;
    }
    // Open-bottom helmet leaves its timber support visible from below.
    add(new THREE.SphereGeometry(.15,12,8,0,Math.PI*2,0,Math.PI*.55),plate,0,1.04,0);
    group.add(shell);
  }
  return group;
}
