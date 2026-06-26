from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.models import Group, Permission
from django.db.models import Avg
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Chapter, ChapterPersonRole, Comment, Episode, Franchise, Genre,
    Person, Playlist, PlaylistChapter, Rating, Review, Subscription,
    UserPaymentMethod, UserSubscription, ViewHistory
)

User = get_user_model()


# ==============================================================================
# 🔐 AUTH SERIALIZERS
# ==============================================================================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Расширенный логин: поддерживает username, email или login_code + password
    """
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['is_staff'] = user.is_staff
        return token
    
    def validate(self, attrs):
        identifier = attrs.get('username')
        password = attrs.get('password')
        
        if not identifier or not password:
            raise serializers.ValidationError(
                _('Поля "username" и "password" обязательны.'),
                code='authorization'
            )
        
        user = authenticate(
            request=self.context.get('request'),
            username=identifier,
            password=password
        )
        
        if user is None:
            user = User.objects.filter(login_code=identifier).first()
            if user and user.check_password(password):
                pass
            else:
                raise serializers.ValidationError(
                    _('Неверные учетные данные.'),
                    code='authorization'
                )
        
        if not user.is_active:
            raise serializers.ValidationError(
                _('Аккаунт деактивирован.'),
                code='authorization'
            )
        
        data = super().validate(attrs)
        
        data.update({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff,
                'avatar': getattr(user, 'avatar', None),
            }
        })
        
        return data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
        extra_kwargs = {
            'username': {'required': True},
            'email': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': _('Пароли не совпадают.')}
            )
        
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError(
                {'username': _('Пользователь с таким именем уже существует.')}
            )
        
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError(
                {'email': _('Пользователь с таким email уже существует.')}
            )
        
        return attrs
    
    def create(self, validated_data):
        from .views import UserViewSet

        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            login_code=UserViewSet._generate_login_code()
        )
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    
    def validate(self, attrs):
        self.token = attrs['refresh']
        return attrs
    
    def save(self, **kwargs):
        try:
            RefreshToken(self.token).blacklist()
        except Exception:
            raise serializers.ValidationError(
                {'refresh': _('Неверный токен.')},
                code='bad_token'
            )


# ==============================================================================
# 👤 USER SERIALIZERS (для обычных пользователей)
# ==============================================================================

class UserBriefSerializer(serializers.ModelSerializer):
    """Краткий сериализатор для вложенных ссылок (комментарии, рейтинги и т.д.)"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class UserDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для просмотра своего профиля"""
    profile_pic_url = serializers.SerializerMethodField()
    groups = serializers.StringRelatedField(many=True, read_only=True)
    is_admin = serializers.SerializerMethodField()  # 👈 Новое поле
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'profile_pic_url', 'description', 'date_joined', 'is_active', 
            'is_staff', 'is_admin', 'groups'  # 👈 Добавили is_admin и is_staff
        ]
        read_only_fields = fields

    def get_profile_pic_url(self, obj):
        if obj.profile_pic:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.profile_pic.url) if request else obj.profile_pic.url
        return None
    
    def get_is_admin(self, obj):
        """Возвращает True, если пользователь является администратором (staff)"""
        return obj.is_staff

class UserUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления профиля самим пользователем"""
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'profile_pic', 'description']

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Этот email уже зарегистрирован в системе.")
        return value


# ==============================================================================
# 🛠️ ADMIN USER SERIALIZERS (для админки)
# ==============================================================================

class GroupBriefSerializer(serializers.ModelSerializer):
    """🏷️ Краткий сериализатор групп (ролей)"""
    class Meta:
        model = Group
        fields = ['id', 'name']
        read_only_fields = fields


class PermissionBriefSerializer(serializers.ModelSerializer):
    """🔑 Краткий сериализатор прав доступа"""
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename']
        read_only_fields = fields


class AdminUserBriefSerializer(serializers.ModelSerializer):
    """
    📋 Сериализатор для списка пользователей в админке.
    Расширенная версия UserBriefSerializer с полями для управления.
    """
    profile_pic_url = serializers.SerializerMethodField()
    groups_list = GroupBriefSerializer(source='groups', many=True, read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'profile_pic_url', 'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login', 'groups_list'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_profile_pic_url(self, obj):
        if obj.profile_pic:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.profile_pic.url) if request else obj.profile_pic.url
        return None


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """
    🔍 Детальный сериализатор пользователя для админки.
    Включает все поля для полного управления.
    """
    profile_pic_url = serializers.SerializerMethodField()
    groups_list = GroupBriefSerializer(source='groups', many=True, read_only=True)
    permissions_list = PermissionBriefSerializer(source='user_permissions', many=True, read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'profile_pic_url', 'description',
            'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login',
            'groups_list', 'permissions_list'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_profile_pic_url(self, obj):
        if obj.profile_pic:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.profile_pic.url) if request else obj.profile_pic.url
        return None


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """
    ✏️ Сериализатор для админского обновления пользователя.
    Позволяет менять все поля, включая права и группы.
    """
    group_ids = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        required=False,
        source='groups',
        help_text='ID групп (ролей), к которым принадлежит пользователь'
    )
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        required=False,
        source='user_permissions',
        help_text='ID специфических прав пользователя'
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'description',
            'is_active', 'is_staff', 'is_superuser',
            'group_ids', 'permission_ids'
        ]
    
    def validate_username(self, value):
        """Проверка уникальности username"""
        if User.objects.filter(username=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Пользователь с таким username уже существует.")
        return value
    
    def validate_email(self, value):
        """Проверка уникальности email"""
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Этот email уже зарегистрирован.")
        return value
    
    def update(self, instance, validated_data):
        """Кастомное обновление с обработкой M2M полей"""
        groups = validated_data.pop('groups', None)
        permissions = validated_data.pop('user_permissions', None)
        
        # Обновляем обычные поля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Обновляем группы (если переданы)
        if groups is not None:
            instance.groups.set(groups)
        
        # Обновляем права (если переданы)
        if permissions is not None:
            instance.user_permissions.set(permissions)
        
        return instance


class AvailableRoleSerializer(serializers.ModelSerializer):
    """
    🏷️ Сериализатор для списка доступных ролей (групп).
    Используется в выпадающих списках на фронте.
    """
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'users_count']
        read_only_fields = fields
    
    def get_users_count(self, obj):
        """Количество пользователей в группе"""
        return obj.user_set.count()


class AvailablePermissionSerializer(serializers.ModelSerializer):
    """
    🔑 Сериализатор для списка доступных прав.
    Сгруппирован по приложениям для удобства.
    """
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'app_label']
        read_only_fields = fields


# ==============================================================================
# 💳 PAYMENT & SUBSCRIPTION
# ==============================================================================

class UserPaymentMethodSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    
    class Meta:
        model = UserPaymentMethod
        fields = ['id', 'user', 'payment_type', 'provider_id', 'masked_card_number', 
                  'card_brand', 'card_expiry_month', 'card_expiry_year', 'added_at', 'valid_until']
        read_only_fields = ['id', 'user', 'added_at', 'valid_until']


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['id', 'title', 'price_usd', 'duration_days', 'description']
        read_only_fields = fields


class UserSubscriptionSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    subscription = SubscriptionSerializer(read_only=True)
    payment_methods = UserPaymentMethodSerializer(many=True, read_only=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'user', 'subscription', 'start_date', 'end_date', 'is_active', 
                  'payment_methods', 'auto_renew', 'created_at', 'updated_at', 'canceled_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'canceled_at']


# ==============================================================================
# 🎬 CONTENT SERIALIZERS
# ==============================================================================

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name']
        read_only_fields = ['id']


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ['id', 'first_name', 'last_name', 'birth_date', 'country', 'photo_url', 'biography']
        read_only_fields = fields


class FranchiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Franchise
        fields = ['id', 'title', 'created_at', 'updated_at']
        read_only_fields = fields


class EpisodeSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField(read_only=True)
    thumbnail_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Episode
        fields = ['id', 'chapter', 'episode_number', 'title', 'video_url', 'duration', 'release_date', 'thumbnail_url']
        extra_kwargs = {'chapter': {'required': False}}

    def get_video_url(self, obj):
        if obj.video_file:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.video_file.url) if request else obj.video_file.url
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail_img:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.thumbnail_img.url) if request else obj.thumbnail_img.url
        return None


class EpisodeBriefSerializer(serializers.ModelSerializer):
    """Краткая информация об эпизоде для списка"""
    thumbnail_url = serializers.ImageField(source='thumbnail_img', read_only=True)
    stream_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Episode
        fields = [
            'id', 'episode_number', 'title', 'thumbnail_url',
            'duration', 'release_date', 'video_file', 'stream_url'
        ]
    
    def get_stream_url(self, obj):
        request = self.context.get('request')
        if request and obj.video_file:
            return request.build_absolute_uri(
                f'/api/v1/video/episodes/{obj.id}/'
            )
        return None


class ChapterSerializer(serializers.ModelSerializer):
    franchise = FranchiseSerializer(read_only=True)
    required_subscription = SubscriptionSerializer(read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    people = PersonSerializer(many=True, read_only=True)
    poster_img_url = serializers.SerializerMethodField(read_only=True)
    franchise_overview = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Chapter
        fields = ['id', 'poster_img_url', 'title', 'release_date', 'rating_cache', 
                  'view_count', 'franchise', 'required_subscription', 'genres', 'people', 'franchise_overview', 'content_type']
        read_only_fields = ['id', 'rating_cache', 'view_count']

    def get_poster_img_url(self, obj):
        if obj.poster_image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.poster_image.url) if request else obj.poster_image.url
        return None

    def get_franchise_overview(self, obj):
        if obj.franchise and hasattr(obj.franchise, 'get_chapter_overview'):
            return obj.franchise.get_chapter_overview()
        return []


class ChapterDetailSerializer(serializers.ModelSerializer):
    """Расширенный сериализатор для страницы фильма/сериала"""
    franchise = FranchiseSerializer(read_only=True)
    required_subscription = SubscriptionSerializer(read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    people = PersonSerializer(many=True, read_only=True)
    episodes = EpisodeBriefSerializer(many=True, read_only=True)
    poster_img_url = serializers.ImageField(source='poster_image', read_only=True)
    trailer_url = serializers.URLField(read_only=True)
    avg_rating = serializers.SerializerMethodField()
    is_in_watchlist = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = Chapter
        fields = [
            'id', 'title', 'description', 'poster_img_url', 'trailer_url',
            'release_date', 'content_type', 'age_rating', 'country',
            'view_count', 'rating_cache', 'avg_rating', 'franchise',
            'required_subscription', 'genres', 'people', 'episodes',
            'chapter_number', 'franchise_relation', 'is_in_watchlist',
            'user_rating', 'content_type'
        ]
    
    def get_avg_rating(self, obj):
        avg = obj.ratings.aggregate(avg=Avg('score'))['avg']
        return round(avg, 2) if avg else 0
    
    def get_is_in_watchlist(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return PlaylistChapter.objects.filter(
                playlist__user=request.user,
                playlist__is_favorite=True,
                chapter=obj
            ).exists()
        return False
    
    def get_user_rating(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            rating = Rating.objects.filter(
                user=request.user, chapter=obj
            ).first()
            return rating.score if rating else None
        return None


class RelatedChapterSerializer(serializers.ModelSerializer):
    """Сериализатор для похожего контента"""
    poster_img_url = serializers.ImageField(source='poster_image', read_only=True)
    avg_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = Chapter
        fields = [
            'id', 'title', 'poster_img_url', 'release_date',
            'avg_rating', 'view_count', 'content_type'
        ]
    
    def get_avg_rating(self, obj):
        avg = obj.ratings.aggregate(avg=Avg('score'))['avg']
        return round(avg, 2) if avg else 0


class ChapterPersonRoleSerializer(serializers.ModelSerializer):
    chapter = ChapterSerializer(read_only=True)
    person = PersonSerializer(read_only=True)

    class Meta:
        model = ChapterPersonRole
        fields = ['id', 'chapter', 'person', 'role']
        read_only_fields = ['id', 'chapter', 'person']


# ==============================================================================
# 💬 INTERACTION SERIALIZERS
# ==============================================================================

class CommentSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    chapter = ChapterSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'chapter', 'text', 'created_at', 'likes_count', 'dislikes_count']
        read_only_fields = ['id', 'user', 'chapter', 'created_at', 'likes_count', 'dislikes_count']

class ReviewSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    # 👇 Отправляем только ID главы, а не полные данные
    chapter = serializers.PrimaryKeyRelatedField(read_only=True)
    chapter_title = serializers.CharField(source='chapter.title', read_only=True)  # Опционально: только название
    
    class Meta:
        model = Review
        fields = [
            'id', 'user', 'chapter', 'chapter_title',  # chapter_title — опционально, если нужно название
            'text', 'created_at', 'likes_count', 'dislikes_count'
        ]
        read_only_fields = [
            'id', 'user', 'chapter', 'chapter_title', 'created_at', 
            'likes_count', 'dislikes_count'
        ]

    def create(self, validated_data):
        # При создании автоматически привязываем к главе (если передан chapter_id)
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class RatingSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    chapter = ChapterSerializer(read_only=True)

    class Meta:
        model = Rating
        fields = ['id', 'user', 'chapter', 'score', 'created_at']
        read_only_fields = ['id', 'user', 'chapter', 'created_at']


# ==============================================================================
# 📚 PLAYLIST & HISTORY
# ==============================================================================

class PlaylistSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)

    class Meta:
        model = Playlist
        fields = ['id', 'user', 'title', 'created_at', 'updated_at', 'is_public', 'cover_image_url', 'slug', 'is_favorite']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'slug']


class PlaylistChapterSerializer(serializers.ModelSerializer):
    playlist = PlaylistSerializer(read_only=True)
    chapter = ChapterSerializer(read_only=True)
    playlist_id = serializers.PrimaryKeyRelatedField(queryset=Playlist.objects.all(), source='playlist', write_only=True)
    chapter_id = serializers.PrimaryKeyRelatedField(queryset=Chapter.objects.all(), source='chapter', write_only=True)

    class Meta:
        model = PlaylistChapter
        fields = ['id', 'playlist', 'playlist_id', 'chapter', 'chapter_id', 'added_at', 'note']
        read_only_fields = ['id', 'playlist', 'chapter', 'added_at']


class ViewHistorySerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    chapter = ChapterSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)
    chapter_id = serializers.PrimaryKeyRelatedField(queryset=Chapter.objects.all(), source='chapter', write_only=True)

    class Meta:
        model = ViewHistory
        fields = ['id', 'user', 'chapter', 'viewed_at', 'user_id', 'chapter_id']
        read_only_fields = ['id', 'user', 'chapter', 'viewed_at']


from .models import CompanySettings


class CompanySettingsSerializer(serializers.ModelSerializer):
    """Сериализатор для админов - полный доступ ко всем полям"""
    
    class Meta:
        model = CompanySettings
        fields = [
            'id',
            'company_name',
            'copyright_text',
            'age_rating',
            'support_text',
            'support_button_text',
            'social_links',
            'footer_poem',
            'updated_at',
            'updated_by',
        ]
        read_only_fields = ['id', 'updated_at', 'updated_by']
    
    def validate_social_links(self, value):
        """Валидация ссылок на соцсети"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("social_links должен быть объектом")
        
        allowed_keys = {'vk', 'telegram', 'youtube', 'ok'}
        for key in value.keys():
            if key not in allowed_keys:
                raise serializers.ValidationError(
                    f"Недопустимая соцсеть: {key}. Допустимы: {', '.join(allowed_keys)}"
                )
        
        # Валидация URL
        from django.core.validators import URLValidator
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        url_validator = URLValidator()
        for key, url in value.items():
            if url:  # Пустые строки пропускаем
                try:
                    url_validator(url)
                except DjangoValidationError:
                    raise serializers.ValidationError(
                        {key: f"Некорректный URL: {url}"}
                    )
        
        return value


class PublicCompanySettingsSerializer(serializers.ModelSerializer):
    """Публичный сериализатор - только читаемые поля для футера"""
    
    class Meta:
        model = CompanySettings
        fields = [
            'company_name',
            'copyright_text',
            'age_rating',
            'support_text',
            'support_button_text',
            'social_links',
            'footer_poem',
        ]
        # Все поля только для чтения
        read_only_fields = fields