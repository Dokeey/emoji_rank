from datetime import datetime

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session, joinedload

from app import schemas
from app.models import User, Reaction
from schemas import UserReceivedReactions, ReceivedEmojiInfo, ReceivedReactionUser

BEST_LOVE = ['heart']
BEST_FUNNY = ['kkkk', '기쁨']
BEST_HELP = ['pray', '기도']
BEST_GOOD = ['+1', 'wow', 'wonderfulk', '천재_개발자']
BEST_BAD = ['eye_shaking']


def get_user(db: Session, item_user: str):
    return db.query(User).filter(User.slack_id == item_user).first()


def get_users(db: Session, year: int, month: int):
    """
    :param year: 년
    :param month: 월
    """
    sub = db.query(Reaction.to_user_id, func.sum(Reaction.count))
    if year and month:
        sub = sub.filter(Reaction.year == year, Reaction.month == month)
    elif year:
        sub = sub.filter(Reaction.year == year)
    elif month:
        sub = sub.filter(Reaction.month == month)
    sub = sub.group_by(Reaction.to_user_id).subquery()

    users = db.query(
        User.id,
        User.avatar_url,
        User.username,
        User.my_reaction,
        func.ifnull(sub.c.get('sum(reactions.count)'), 0).label('received_reaction')
    ).outerjoin(
        sub, and_(sub.c.to_user_id == User.id)
    ).order_by(
        desc('received_reaction')
    ).all()

    user_infos = []
    for user in users:
        user_infos.append(
            ReceivedReactionUser(
                id=user.id,
                avatar_url=user.avatar_url,
                username=user.username,
                my_reaction=user.my_reaction,
                received_reaction=user.received_reaction
            )
        )

    return user_infos


def get_my_reaction(db: Session, slack_id: str, year: int, month: int):

    reactions = db.query(Reaction).options(
        joinedload(Reaction.from_user),
        joinedload(Reaction.to_user),
    ).filter(
        Reaction.to_user.has(slack_id=slack_id),
    )

    if year:
        reactions = reactions.filter(Reaction.year == year)
    if month:
        reactions = reactions.filter(Reaction.month == month)

    reaction_data = {}
    for reaction in reactions:
        if not reaction_data.get(reaction.type):
            reaction_data[reaction.type] = reaction.count
        else:
            reaction_data[reaction.type] += reaction.count

    return reaction_data


def get_reactions(db: Session, user_id: int, year: int, month: int):
    """
    :param user_id: 유저 ID
    :param year: 년
    :param month: 월
    """

    reactions = db.query(Reaction).options(
        joinedload(Reaction.from_user),
        joinedload(Reaction.to_user),
    ).filter(
        Reaction.to_user_id == user_id,
    )

    if year:
        reactions = reactions.filter(Reaction.year == year)
    if month:
        reactions = reactions.filter(Reaction.month == month)

    reaction_data = {}
    for reaction in reactions:
        from_user_name = reaction.from_user.username
        if not reaction_data.get(from_user_name):
            reaction_data[from_user_name] = {
                'emoji_infos': [ReceivedEmojiInfo(type=reaction.type, count=reaction.count)]
            }
        else:
            reaction_data[from_user_name]['emoji_infos'].append(
                ReceivedEmojiInfo(type=reaction.type, count=reaction.count)
            )

    return [UserReceivedReactions(username=key, emoji=value.get('emoji_infos')) for key, value in reaction_data.items()]


def create_user(db: Session, user: schemas.UserCreate):
    db_user = User(slack_id=user.slack_id, username=user.username, avatar_url=user.avatar_url)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def update_added_reaction(db: Session, type: str, item_user: str, user: str, is_increase: bool):
    """
    :param item_user: 리액션을 받는 유저 -> to_user
    :param type: 리액션 타입(이모지 종류) -> from_user
    :param user: 리액션을 한 유저
    :param is_increase: True: Added, False: Removed
    """
    from_user = db.query(User).filter(User.slack_id == user).one_or_none()
    to_user = db.query(User).filter(User.slack_id == item_user).one_or_none()

    if to_user is None or from_user is None:
        return

    now_date = datetime.now().date()
    reaction = db.query(Reaction).filter(
        Reaction.year == now_date.year, Reaction.month == now_date.month,
        Reaction.from_user == from_user.id, Reaction.to_user == to_user.id,
        Reaction.type == type
    ).first()

    """
    1. 리액션이 있는경우 (remove 인 경우 받은 reaction이 0개 인 경우 return)
    2  리액션이 없는데 감소 해야하는 경우 return
    3. 리액션이 없는데 증가해야하는 경우
    """
    if reaction:
        if is_increase is False and reaction.count == 0:
            return
        reaction.count += 1 if is_increase else -1
    elif is_increase:
        reaction = Reaction(
            year=now_date.year,
            month=now_date.month,
            type=type,
            from_user=from_user.id,
            to_user=to_user.id
        )
        reaction.count = 1
    else:
        return

    db.add(reaction)
    db.commit()
    db.refresh(reaction)


def update_my_reaction(db: Session, user: User, is_increase: bool):
    """
    내가 가지고 있는 reaction count 업데이트
    :param is_increase: True: Added, False: Removed
    """
    user.my_reaction += 1 if is_increase else -1

    db.add(user)
    db.commit()
    db.refresh(user)


def get_member_reaction_count(db: Session, user: User, year: int, month: int):
    """
    멤버가 받은 reaction을 현재 prise type별로 가지고 오는 함수
    {user_id : '123123', love : 3, funny : 5, help : 5, good : 10, bad : 5}
    """

    # 리액션별로 count
    reaction_list = db.query(Reaction).filter(
        Reaction.to_user_id == user.id,
        Reaction.year == year,
        Reaction.month == month
    )

    result = {
        'username': user.username,
        'love': 0,
        'funny': 0,
        'help': 0,
        'good': 0,
        'bad': 0,
    }

    for reaction in reaction_list:
        if reaction.type in BEST_LOVE:
            result['love'] += 1
        elif reaction.type in BEST_FUNNY:
            result['funny'] += 1
        elif reaction.type in BEST_HELP:
            result['help'] += 1
        elif reaction.type in BEST_GOOD:
            result['help'] += 1
        elif reaction.type in BEST_BAD:
            result['bad'] += 1

    return result
