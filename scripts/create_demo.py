"""Create an entirely synthetic editable archive for browser checks."""
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openpyxl import Workbook
from qq_collection_backup.editable_export import write_editable

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    workbook=Workbook();workbook.active.append(['人工演示数据']);workbook.save(args.output/'收藏索引.xlsx')
    groups=['技术宅','游戏','动画与漫画','影视','备忘录','生活记录','链接','存档','阅读摘录','未分组']
    records=[]
    for index in range(85):
        group=groups[index%len(groups)]
        text='这是人工构造的演示收藏，不来自 QQ 账号。\n可以按分组检索，展开阅读，或修改正文后保存到本地 Markdown。\n\n保留必要的段落与换行，压缩操作区和重复信息。'
        records.append({'id':f'demo-{index+1}','title':'本地笔记整理示例' if index==0 else f'{group}演示笔记',
                        'text':text,'number':index+1,'date':'2026-11-18 12:00:00','type':'文字','status':'列表文字',
                        'qq_group':group,'qq_group_id':str(index%len(groups)),'source':'演示来源','sender':'演示发送者',
                        'url':'','notes':'','attachments':[],'preview':text,'detail_html':''})
    write_editable({'records':records,'groups':[{'name':name} for name in groups]},args.output/'可编辑收藏',args.output/'missing')
    print('Synthetic demo created.')

if __name__=='__main__':main()
