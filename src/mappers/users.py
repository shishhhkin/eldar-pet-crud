from src.mappers.base import apply_fields
from src.models.user_profiles import UserProfileModel
from src.models.users import UserModel
from src.schemas.users import UserCreate, UserRead, UserUpdate


def to_user_model(payload: UserCreate) -> UserModel:
    return UserModel(
        **payload.model_dump(mode='json', exclude={'profile'}),
        profile=UserProfileModel(**payload.profile.model_dump(mode='json')),
    )


def apply_user_update(user: UserModel, payload: UserUpdate) -> None:
    apply_fields(user, payload, exclude={'profile'})
    if payload.profile is not None:
        profile_data = payload.profile.model_dump(mode='json')
        if user.profile is None:
            user.profile = UserProfileModel(**profile_data)
        else:
            for key, value in profile_data.items():
                setattr(user.profile, key, value)


def to_user_read(user: UserModel) -> UserRead:
    return UserRead.model_validate(user)
