"""Explicit local seed. All names/classes are invented; never overwrites accounts."""
from pathlib import Path
import argparse
from app.platform import Platform


def seed(database_url):
    platform = Platform(database_url)
    accounts = [
        ('S001','小林','student','DemoStudent123!','DEMO7',[]),
        ('S002','小禾','student','DemoStudent123!','DEMO7',[]),
        ('T001','示例教师','teacher','DemoTeacher123!','',['DEMO7']),
    ]
    for user_id,name,role,password,class_id,class_ids in accounts:
        try:
            platform.create_account(user_id,name,role,password,class_id,class_ids,True)
            print(f'虚构验收账号 {user_id} / {name} / {password}')
        except ValueError as exc:
            print(f'{user_id}: {exc}')
    print('仅供本机合成数据验收，不是真实师生。不要把此演示账号部署到公网。')


if __name__ == '__main__':
    root=Path(__file__).resolve().parents[1]
    (root/'data').mkdir(exist_ok=True)
    parser=argparse.ArgumentParser()
    parser.add_argument('--database-url',default=f'sqlite:///{root / "data" / "platform.sqlite"}')
    seed(parser.parse_args().database_url)
