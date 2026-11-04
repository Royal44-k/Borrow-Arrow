export const ACTOR_ASSETS = {
 support: {file:'cast-support-s11.png',columns:4,width:2056,height:765},
 principal: {file:'cast-principal-s11.png',columns:3,width:1774,height:887},
 shen: {file:'shen-yan.png',columns:1,width:1024,height:1536},
} as const;
export type ActorId='hanbo'|'acheng'|'zhouyu'|'watchman'|'lusu'|'zhuge'|'cao'|'shen';
export interface ActorIdentity {id:ActorId;atlas:keyof typeof ACTOR_ASSETS;frame:number;name:string}
const CAST:ActorIdentity[]=[
 {id:'hanbo',atlas:'support',frame:0,name:'韩伯'},
 {id:'acheng',atlas:'support',frame:1,name:'阿成'},
 {id:'zhouyu',atlas:'support',frame:2,name:'周瑜'},
 {id:'watchman',atlas:'support',frame:3,name:'哨长'},
 {id:'lusu',atlas:'principal',frame:0,name:'鲁肃'},
 {id:'zhuge',atlas:'principal',frame:1,name:'诸葛亮'},
 {id:'cao',atlas:'principal',frame:2,name:'曹操'},
 {id:'shen',atlas:'shen',frame:0,name:'沈砚'},
];
const ALIASES:Record<ActorId,string[]>={
 hanbo:['韩伯','船夫','老船夫','船工','船夫韩伯','船工韩伯','老船夫韩伯'],
 acheng:['阿成','鼓手','鼓手阿成'],
 zhouyu:['周瑜','周都督'],
 watchman:['哨长','曹军哨长','曹营哨长','岸上军士','岸上弓手','曹军弓手','弓手'],
 lusu:['鲁肃','子敬','鲁子敬'],
 zhuge:['诸葛亮','孔明','诸葛孔明','诸葛先生'],
 cao:['曹操','曹丞相'],
 shen:['沈砚','书佐沈砚','同行书佐沈砚'],
};
/** Match a speaker label, never arbitrary dialogue mentioning somebody's name. */
export function resolveActor(speaker:string):ActorIdentity|null {
 const name=speaker.trim().replace(/[（(][^）)]*[）)]$/u,'').replace(/[\s·・]/gu,'');
 return CAST.find(actor=>ALIASES[actor.id].includes(name))??null;
}
export function actorVisibleInMode(mode:string|undefined):boolean {
 return !['drum','helm','collect','fire','return'].includes(mode??'story');
}
