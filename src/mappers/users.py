from src.mappers.base import apply_fields
from src.models.user_profiles import UserProfileModel
from src.models.users import UserModel
from src.schemas.users import UserProfilePayload, UserRead, UserUpdate


def to_user_profile_model(payload: UserProfilePayload) -> UserProfileModel:
    return UserProfileModel(**payload.model_dump(mode='json'))


def apply_user_update(user: UserModel, payload: UserUpdate) -> None:
    apply_fields(user, payload, exclude={'profile'})
    if payload.profile is not None:
        if user.profile is None:
            user.profile = to_user_profile_model(payload.profile)
        else:
            for key, value in payload.profile.model_dump(mode='json').items():
                setattr(user.profile, key, value)


def to_user_read(user: UserModel) -> UserRead:
    return UserRead.model_validate(user)
