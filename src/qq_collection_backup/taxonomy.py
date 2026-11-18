"""Offline vocabulary and conservative suggestions, never semantic-review claims."""
import re,unicodedata,copy

DOMAINS=['待辨识','游戏','动画','漫画','漫威','影视与特摄','音乐','技术宅','学习与知识','生活','社会与人文','文学与情感','杂谈','个人资料']
PURPOSES=['待辨识','观点讨论','生活吐槽','备忘录','日记与经历','摘要与摘录','教程与方法','清单与推荐','数据整理','资源与链接','存档','重要账号密码','个人信息存档','段子与玩梗','表情包与图片']
GROUP_DOMAINS={'数码科技':'技术宅','电脑':'技术宅','硬件':'技术宅','技术':'技术宅','游戏':'游戏','动画':'动画','动漫':'动画','漫画':'漫画','超英美漫':'漫威','美漫':'漫威','漫威':'漫威','特摄':'影视与特摄','影视剧':'影视与特摄','影视':'影视与特摄','音乐':'音乐','生活':'生活','情感':'文学与情感','文学':'文学与情感','知识':'学习与知识','学习':'学习与知识','杂谈':'杂谈'}
CONCEPTS={
 '技术宅':{'电脑硬件':['显卡','主板','处理器','内存条','电源功率'],'软件工具':['开源软件','插件','命令行','脚本','软件安装'],'编程':['编程','python','javascript','typescript','代码调试'],'网络配置':['路由器','代理配置','局域网','dns','端口转发'],'数据备份':['备份','数据库','数据迁移','同步笔记'],'人工智能':['大模型','提示词','深度学习','人工智能','llm']},
 '游戏':{'游戏设计':['关卡设计','战斗系统','玩法设计','数值设计'],'游戏攻略':['通关','配队','攻略','装备搭配'],'游戏清单':['游戏推荐','游戏列表','游戏清单'],'视觉小说':['视觉小说','galgame','gal game']},
 '动画':{'动画资料':['动画目录','动画资料','动画列表','动画统计'],'作品评价':['作品评价','动画评价','叙事结构']},
 '漫画':{'漫画资料':['漫画目录','漫画连载','漫画推荐']},
 '漫威':{'美漫':['美漫','漫威','marvel','dc漫画'],'设定资料':['设定集','宇宙编号','能力设定']},
 '影视与特摄':{'特摄':['假面骑士','奥特曼','超级战队','特摄'],'影视评价':['影评','电影评价','电视剧评价']},
 '音乐':{'音乐推荐':['歌单','音乐推荐','专辑推荐'],'音乐理论':['和弦','乐理','编曲']},
 '生活':{'生活经验':['生活经验','生活技巧'],'健康常识':['睡眠','锻炼','饮食习惯'],'消费记录':['消费记录','购物清单','预算']},
 '学习与知识':{'学习方法':['学习方法','记忆方法','复习计划'],'知识整理':['知识整理','概念解释','资料汇总']},
 '文学与情感':{'情感表达':['情感表达','感情经历'],'阅读摘录':['读书摘录','书摘','诗句']},
 '杂谈':{'观点记录':['观点记录','随想'],'网络文化':['网络文化','网络梗','流行语']}}
ENTITIES={'原神':r'原神','崩坏星穹铁道':r'崩坏[：:\s]*星穹铁道|星穹铁道','传颂之物':r'传颂之物','Muv-Luv':r'muv[\s\-]*luv','喜羊羊与灰太狼':r'喜羊羊与灰太狼','假面骑士':r'假面骑士','奥特曼':r'奥特曼','漫威':r'漫威|\bmarvel\b','DC漫画':r'DC漫画|DC宇宙','Python':r'\bpython\b','Obsidian':r'\bobsidian\b','Windows':r'\bwindows\b'}

def label(value,limit=40):
 if not isinstance(value,str):raise ValueError('分类名称应为文字。')
 value=unicodedata.normalize('NFKC',value).strip()
 if not value or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError(f'名称需为1至{limit}字的单行文字。')
 return value

def tags(values):
 if not isinstance(values,list) or len(values)>3:raise ValueError('标签最多3个，也可以留空。')
 result=[];seen=set()
 for value in values:
  value=label(value,24).lstrip('#').strip()
  if not value:raise ValueError('标签不能为空。')
  if value.casefold() not in seen:result.append(value);seen.add(value.casefold())
 return result

def classification(value):
 if not isinstance(value,dict):raise ValueError('分类或标签格式不正确。')
 return {'domain':label(value.get('domain')),'purpose':label(value.get('purpose')),'tags':tags(value.get('tags'))}

def vocabulary(records=(),store=None,previous=None):
 previous=previous or {};custom=(store or {}).get('taxonomy',{})
 domains=list(DOMAINS)+previous.get('domains',[])+custom.get('domains',[])
 purposes=list(PURPOSES)+previous.get('purposes',[])+custom.get('purposes',[])
 for record in records:
  a=record.get('classification',{});domains.append(a.get('domain','待辨识'));purposes.append(a.get('purpose','待辨识'))
 for edit in (store or {}).get('edits',{}).values():
  a=edit.get('classification',{});domains.append(a.get('domain','待辨识'));purposes.append(a.get('purpose','待辨识'))
 return {'domains':list(dict.fromkeys(domains)),'purposes':list(dict.fromkeys(purposes))}

def suggest(record):
 """Use whole cached text + QQ group and structure; ambiguity stays explicit."""
 text=record.get('text','');title=record.get('title','');group=record.get('qq_group','');low=(title+'\n'+text).casefold()
 domain=group if group in DOMAINS else GROUP_DOMAINS.get(group,'待辨识');purpose='待辨识';found=[];related=[];why=[]
 if domain!='待辨识':why.append('QQ分组提供领域线索')
 # Keep credentials out of automatic keyword extraction, summaries and previews.
 secret=bool(re.search(r'(?:密码|口令|password|secret|token|api[_ -]?key)\s*[:：=]\s*\S{4,}',text,re.I))
 if secret:return {'domain':'个人资料','purpose':'重要账号密码','tags':[],'related_domains':[],'useful':True,'sensitive':True,'review':True,'confidence':'待确认','review_method':'本地规则建议，未逐条复核','reason':'检测到凭据字段格式；只作本地遮挡和待确认提示，不提取秘密为标签。','flags':['未逐条复核']}
 scores={name:sum(1 for terms in concepts.values() for term in terms if term.casefold() in low) for name,concepts in CONCEPTS.items()}
 if domain=='待辨识' and scores:
  ranked=sorted(scores,key=scores.get,reverse=True)
  if scores[ranked[0]]>=2 and scores[ranked[0]]>scores[ranked[1]]:domain=ranked[0];why.append('正文中有多项同领域线索')
 if re.search(r'喜羊羊与灰太狼|动画(?:目录|信息|统计|列表)|\d+\s*部\s*(?:TV|动画)',text,re.I) and domain!='漫威':
  domain='动画';related=['漫画'];purpose='数据整理';why.append('动画条目及数量整理结构')
 lines=[line.strip() for line in text.splitlines() if line.strip()]
 list_lines=sum(bool(re.match(r'^(?:[-*•·]|\d+[.、)）]|[一二三四五六七八九十]+[、.])',line)) for line in lines)
 data_lines=sum(bool(re.search(r'\d+\s*(?:部|作|季|集|卷|话|年)|(?:TV|OVA|OAD|剧场版)',line,re.I)) for line in lines)
 if purpose=='待辨识':
  if len(lines)>=4 and data_lines>=3:purpose='数据整理';why.append('多行作品或数量统计')
  elif len(lines)>=4 and list_lines>=3:purpose='清单与推荐';why.append('多条清单结构')
  elif re.search(r'(?:教程|操作步骤|使用方法|安装步骤|配置步骤)|(?:第一步|步骤\s*1).*(?:第二步|步骤\s*2)',text,re.S):purpose='教程与方法';why.append('操作步骤结构')
  elif re.search(r'^(?:待办|备忘|明天记得|记得要|TODO)[:：\s]',text,re.I) or group=='备忘录':purpose='备忘录';why.append('明确备忘标记或分组')
  elif group in ['梗语录','段子','梗']:purpose='段子与玩梗';why.append('QQ分组标明梗或语录，未推断具体梗来源')
  elif re.fullmatch(r'\s*https?://\S+\s*',text):purpose='资源与链接';why.append('正文只有链接')
  elif re.search(r'^(?:书摘|摘录|摘要|引用)[:：]',text):purpose='摘要与摘录';why.append('明确摘录标记')
  elif re.search(r'^(?:日记|今日记录|今天的记录)[:：\s]',text):purpose='日记与经历';why.append('明确日记标记')
  elif domain=='技术宅':purpose='存档'
 if domain in ('动画','漫画'):related=[d for d in ['动画','漫画'] if d!=domain]
 if text.strip() and not secret and purpose!='资源与链接':
  for name,pattern in ENTITIES.items():
   matches=len(re.findall(pattern,text,re.I))
   if matches and (matches>1 or re.search(pattern,title,re.I) or domain in ['游戏','动画','漫画','漫威','技术宅','影视与特摄']):found.append((min(matches,5)+2,name))
  for name,terms in CONCEPTS.get(domain,{}).items():
   hits=sum(term.casefold() in low for term in terms)
   if hits>=2:found.append((hits,name))
  found=[name for _,name in sorted(found,key=lambda pair:-pair[0])]
 return {'domain':domain,'purpose':purpose,'tags':list(dict.fromkeys(found))[:3],'related_domains':related,'useful':bool(text.strip()),'sensitive':False,'review':bool(text.strip()),'confidence':'待确认','review_method':'本地规则建议，未逐条复核','reason':'；'.join(why) if why else '线索不足，保留待辨识；不按单个词强行归类。','flags':['未逐条复核'] if text.strip() else []}

def initial(record,previous=None):
 if previous and previous.get('text')==record.get('text') and previous.get('title')==record.get('title'):
  a=previous.get('classification',{})
  if a.get('review_method') in ['完整正文语义复核','用户手动调整','人工复核']:return copy.deepcopy(a)
 return suggest(record)
