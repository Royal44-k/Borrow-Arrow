"""Local administrator CLI only. No public teacher registration endpoint."""
import argparse
from getpass import getpass
from pathlib import Path
from app.platform import Platform


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    (root/'data').mkdir(exist_ok=True)
    p=argparse.ArgumentParser(description='在本机创建课件账号，不覆盖已有账号。')
    p.add_argument('--user-id',required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--role',choices=['student','teacher'],required=True)
    p.add_argument('--class-id',default='')
    p.add_argument('--classes',default='',help='教师所授班级，逗号分隔')
    args=p.parse_args()
    password=getpass('密码（至少10位，不显示）: ')
    if password!=getpass('再次输入: '): raise SystemExit('两次密码不同，未创建。')
    platform=Platform(f'sqlite:///{root / "data" / "platform.sqlite"}')
    platform.create_account(args.user_id,args.name,args.role,password,args.class_id,[s.strip() for s in args.classes.split(',') if s.strip()])
    print('已创建；密码未写入明文文件。')
