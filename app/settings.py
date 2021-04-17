from dataclasses import dataclass


@dataclass
class DataBaseSettings:
    HOST = 'HOST'
    PORT = 3306
    DATABASE = 'DATABASE'
    USERNAME = 'USERNAME'
    PASSWORD = 'PASSWORD'


# Reaction Setting
DAY_MAX_REACTION = 5 # 하루 최대 사용할 수 있는 reaction 개수
REACTION_LIST = ['heart'] # reaction type(emoji name), 다른 Emoji 입력도 허용하려면 리스트에 추가하면 된다.
