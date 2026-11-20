const form=document.getElementById('clipForm');
const statusBox=document.getElementById('status');
const submitBtn=document.getElementById('submitBtn');
document.getElementById('video').addEventListener('change',e=>{
  document.getElementById('fileName').textContent=e.target.files[0]?.name||'No file selected';
});
form.addEventListener('submit',async e=>{
  e.preventDefault();
  const file=document.getElementById('video').files[0];
  if(!file){statusBox.textContent='Please select a video file.';return;}
  const data=new FormData(form);
  submitBtn.disabled=true;submitBtn.textContent='✦ Analysing video…';
  statusBox.textContent='Uploading and analysing. This can take several minutes, especially on a large video.';
  document.getElementById('results').classList.add('hidden');
  try{
    const response=await fetch('/api/process',{method:'POST',body:data});
    const result=await response.json();
    if(!response.ok)throw new Error(result.error||'Processing failed');
    const grid=document.getElementById('clipGrid');grid.innerHTML='';
    result.clips.forEach(c=>{
      const card=document.createElement('article');card.className='clip-card';
      const title=document.createElement('h3');title.textContent=c.title;
      const caption=document.createElement('p');caption.textContent=c.caption;
      const meta=document.createElement('div');meta.className='clip-meta';meta.textContent=`${c.start}s – ${c.end}s · ${c.duration}s`;
      const tags=document.createElement('p');tags.textContent=c.hashtags;
      const link=document.createElement('a');link.href=`/download/${result.job_id}/${c.filename}`;link.textContent='Download MP4 ↓';
      const num=document.createElement('div');num.className='clip-number';num.textContent=`CLIP 0${c.number}`;
      card.append(num,title,meta,caption,tags,link);grid.append(card);
    });
    document.getElementById('zipLink').href=result.zip_url;
    document.getElementById('results').classList.remove('hidden');
    statusBox.textContent='Done! Review your five clips below.';
    document.getElementById('results').scrollIntoView({behavior:'smooth'});
  }catch(err){statusBox.textContent='Error: '+err.message;}
  finally{submitBtn.disabled=false;submitBtn.textContent='✦ Find my best 5 clips';}
});
