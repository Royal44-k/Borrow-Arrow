import * as T from 'three'
/** Low spatial frequencies and derivative-filtered glints prevent distant shimmer. */
export function riverMaterial(){return new T.ShaderMaterial({uniforms:{time:{value:0}},vertexShader:`varying vec3 world;void main(){vec4 p=modelMatrix*vec4(position,1.);world=p.xyz;gl_Position=projectionMatrix*viewMatrix*p;}`,fragmentShader:`uniform float time;varying vec3 world;
void main(){vec2 p=world.xz;float wave=sin(p.x*.65+p.y*.42+time*.32)*.025+sin(p.y*.85-time*.25)*.014;vec3 n=normalize(vec3(wave,1.,wave*.6));vec3 v=normalize(cameraPosition-world);float fres=pow(1.-max(dot(n,v),0.),3.);vec3 color=mix(vec3(.025,.061,.08),vec3(.13,.21,.25),fres);float phase=p.y*2.2+sin(p.x*.45+time*.16);float bandLimit=1.-smoothstep(.25,1.2,fwidth(phase));float line=pow(.5+.5*sin(phase),5.)*bandLimit;color+=line*vec3(.009,.015,.018);float fog=1.-exp(-length(cameraPosition-world)*.009);gl_FragColor=vec4(mix(color,vec3(.045,.09,.12),fog),1.);}`})}

