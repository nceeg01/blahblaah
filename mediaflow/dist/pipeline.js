export const fields=['id','title','platform','published_at','views','engagements'];
export const aliases={id:['id','content_id','video_id'],title:['title','name','headline'],platform:['platform','channel','source'],published_at:['published_at','date','publish_date'],views:['views','view_count','plays'],engagements:['engagements','interactions','likes']};
export function parseCSV(text){
 const rows=[];let row=[],cell='',quoted=false,closed=false;
 text=text.replace(/^\uFEFF/,'');
 for(let i=0;i<text.length;i++){const c=text[i];if(quoted){if(c==='"'&&text[i+1]==='"'){cell+='"';i++;}else if(c==='"'){quoted=false;closed=true;}else cell+=c;}else if(c==='"'){if(cell||closed)throw Error('Unexpected quote in CSV.');quoted=true;}else if(c===','||c==='\n'||c==='\r'){row.push(cell);cell='';closed=false;if(c!==','){if(c==='\r'&&text[i+1]==='\n')i++;if(row.some(v=>v.trim()))rows.push(row);row=[];}}else{if(closed)throw Error('Unexpected text after closing CSV quote.');cell+=c;}}
 if(quoted)throw Error('CSV has an unclosed quoted field.');if(cell||row.length||closed){row.push(cell);if(row.some(v=>v.trim()))rows.push(row);}
 if(rows.length<2)throw Error('Include a header and at least one data row.');const headers=rows.shift().map(x=>x.trim());if(headers.some(x=>!x)||new Set(headers).size!==headers.length)throw Error('CSV headers must be nonempty and unique.');
 return rows.map((r,i)=>{if(r.length!==headers.length)throw Error(`CSV row ${i+2}: expected ${headers.length} columns, found ${r.length}.`);return Object.fromEntries(headers.map((h,j)=>[h,r[j]]));});
}
export function parseInput(text,format){let rows;if(format==='csv')rows=parseCSV(text);else{try{rows=JSON.parse(text);}catch{throw Error('Invalid JSON. Use an array of record objects.');}}
 if(!Array.isArray(rows)||!rows.length||rows.some(r=>!r||typeof r!=='object'||Array.isArray(r)))throw Error('Provide a nonempty array of record objects.');if(rows.length>10000)throw Error('Maximum 10,000 records per run.');return rows;
}
export function autoMap(rows){const keys=[...new Set(rows.flatMap(Object.keys))];return Object.fromEntries(fields.map(f=>[f,keys.find(k=>aliases[f].includes(k.trim().toLowerCase()))||'']));}
const norm=v=>String(v??'').trim().replace(/\s+/g,' ');
function number(v){const s=norm(v);if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(s))return null;const n=Number(s.replaceAll(',',''));return Number.isSafeInteger(n)?n:null;}
function date(v){const s=norm(v);if(!/^\d{4}-\d{2}-\d{2}$/.test(s))return null;const d=new Date(s+'T00:00:00Z');return Number.isFinite(+d)&&d.toISOString().slice(0,10)===s?s:null;}
export function transform(rows,mapping){
 const missing=fields.filter(f=>!mapping[f]);if(missing.length)throw Error('Map required fields: '+missing.join(', '));
 const accepted=[],rejected=[],duplicates=[],seen=new Set();
 rows.forEach((raw,i)=>{const r=Object.fromEntries(fields.map(f=>[f,norm(raw[mapping[f]])]));r.platform=r.platform.toLowerCase();const errors=[];
 for(const f of ['id','title','platform'])if(!r[f])errors.push(`${f} is required`);
 const published=date(r.published_at),views=number(r.views),engagements=number(r.engagements);
 if(!published)errors.push('published_at must be a real YYYY-MM-DD date');if(views===null)errors.push('views must be a nonnegative whole number');if(engagements===null)errors.push('engagements must be a nonnegative whole number');
 if(errors.length){rejected.push({row:i+1,errors,raw});return;}
 const key=JSON.stringify([r.platform,r.id]);if(seen.has(key)){duplicates.push({row:i+1,errors:['Duplicate platform + id; first valid record kept'],raw});return;}seen.add(key);
 accepted.push({...r,published_at:published,views,engagements,engagement_rate:views?Math.round(engagements/views*10000)/100:null});});
 return {input:rows.length,accepted,rejected,duplicates};
}
export function toCSV(rows){if(!rows.length)return '';const keys=Object.keys(rows[0]);const quote=v=>'"'+String(v??'').replace(/^[=+\-@\t\r]/,"'$&").replaceAll('"','""')+'"';return [keys.map(quote).join(','),...rows.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\r\n');}
export const sample=[
 {content_id:'M-001',headline:'  Inside the city studio  ',channel:'YouTube ',date:'2026-08-01',plays:'12,400',interactions:'620'},
 {content_id:'M-002',headline:'A morning in Kathmandu',channel:'INSTAGRAM',date:'2026-08-02',plays:'8300',interactions:'740'},
 {content_id:'M-003',headline:'The making of a short film',channel:'YouTube',date:'2026-08-03',plays:'19600',interactions:'1100'},
 {content_id:'M-004',headline:'Five frames, one story',channel:'TikTok',date:'2026-08-04',plays:'32100',interactions:'2800'},
 {content_id:'M-005',headline:'Weekend sound check',channel:'Instagram',date:'2026-08-05',plays:'4600',interactions:'310'},
 {content_id:'M-006',headline:'Meet the editor',channel:'YouTube',date:'2026-08-06',plays:'7200',interactions:'280'},
 {content_id:'M-003',headline:'Duplicate delivery',channel:'youtube',date:'2026-08-03',plays:'19600',interactions:'1100'},
 {content_id:'M-007',headline:'Invalid date example',channel:'TikTok',date:'2026-02-30',plays:'420',interactions:'20'},
 {content_id:'M-008',headline:'',channel:'Instagram',date:'2026-08-08',plays:'850',interactions:'32'},
 {content_id:'M-009',headline:'Negative views example',channel:'YouTube',date:'2026-08-09',plays:'-14',interactions:'3'},
 {content_id:'M-010',headline:'A new series begins',channel:'TikTok',date:'2026-08-10',plays:'0',interactions:'0'},
 {content_id:'M-011',headline:'Behind the microphone',channel:'Instagram',date:'2026-08-11',plays:'5600',interactions:'390'}
];
