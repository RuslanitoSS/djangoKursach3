from rest_framework import serializers
from .models import User, ViewHistory, UserPaymentMethod, PlaylistChapter, Subscription, UserSubscription, Genre, Franchise, Chapter, Episode, Person, ChapterPersonRole, Comment, Review, Rating, Playlist


class UserSerializer(serializers.ModelSerializer):
    profile_pic_url = serializers.ImageField(source='user_profile_pics', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'profile_pic_url',
            'description', 'login_code', 'groups', 'user_permissions'
        ]

class UserPaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPaymentMethod
        fields = ['id', 'user', 'payment_type', 'provider_id', 'masked_card_number', 'card_brand', 'card_expiry_month', 'card_expiry_year', 'added_at', 'valid_until']

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['id', 'title', 'price_usd', 'duration_days', 'description']

class UserSubscriptionSerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer()
    payment_methods = UserPaymentMethodSerializer(many=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'user', 'subscription', 'start_date', 'end_date', 'is_active', 'payment_methods', 'auto_renew', 'created_at', 'updated_at', 'canceled_at']

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name']

class FranchiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Franchise
        fields = ['id', 'title', 'created_at', 'updated_at']

class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ['id', 'first_name', 'last_name', 'birth_date', 'country', 'photo_url', 'biography']

class ChapterSerializer(serializers.ModelSerializer):
    # Добавляем поля для сериализации связанных объектов
    franchise = FranchiseSerializer()  # Сериализуем связанную франшизу
    required_subscription = SubscriptionSerializer()  # Сериализуем подписку
    genres = GenreSerializer(many=True)  # Сериализуем жанры (многие ко многим)
    people = PersonSerializer(many=True)  # Сериализуем людей (многие ко многим)
    poster_img_url = serializers.ImageField(source='chapter_posters', read_only=True)

    # Новый метод для получения информации о франшизе
    franchise_overview = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = ['id', 'poster_img_url' , 'title', 'release_date', 'rating_cache', 'view_count', 'franchise', 'required_subscription', 'genres', 'people', 'franchise_overview']

    def get_franchise_overview(self, obj):
        # Получаем франшизу, к которой относится глава
        franchise = obj.franchise
        if franchise:
            return franchise.get_chapter_overview()  # Используем метод get_chapter_overview() из модели Franchise
        return []  # Если франшиза не указана, возвращаем пустой список

class EpisodeSerializer(serializers.ModelSerializer):
    video_url = serializers.FileField(source='episode_videos', read_only=True)
    thumbnail_url = serializers.ImageField(source='episode_thumbnail_imgs', read_only=True)

    class Meta:
        model = Episode
        fields = [
            'id', 'chapter', 'episode_number', 'title',
            'video_url', 'duration', 'release_date',
            'thumbnail_url'
        ]


class ChapterPersonRoleSerializer(serializers.ModelSerializer):
    chapter = ChapterSerializer()
    person = PersonSerializer()

    class Meta:
        model = ChapterPersonRole
        fields = ['id', 'chapter', 'person', 'role']

class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    chapter = ChapterSerializer()

    class Meta:
        model = Comment
        fields = ['id', 'user', 'chapter', 'text', 'created_at', 'likes_count', 'dislikes_count']

class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    chapter = ChapterSerializer()

    class Meta:
        model = Review
        fields = ['id', 'user', 'chapter', 'text', 'created_at', 'likes_count', 'dislikes_count']

class RatingSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    chapter = ChapterSerializer()

    class Meta:
        model = Rating
        fields = ['id', 'user', 'chapter', 'score', 'created_at']

class PlaylistSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Playlist
        fields = ['id', 'user', 'title', 'created_at', 'updated_at', 'is_public', 'cover_image_url', 'slug', 'is_favorite']

class PlaylistChapterSerializer(serializers.ModelSerializer):
    playlist = PlaylistSerializer(read_only=True)
    chapter = ChapterSerializer(read_only=True)
    playlist_id = serializers.PrimaryKeyRelatedField(queryset=Playlist.objects.all(), source='playlist', write_only=True)
    chapter_id = serializers.PrimaryKeyRelatedField(queryset=Chapter.objects.all(), source='chapter', write_only=True)

    class Meta:
        model = PlaylistChapter
        fields = ['id', 'playlist', 'playlist_id', 'chapter', 'chapter_id', 'added_at', 'note']


class ViewHistorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    chapter = ChapterSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)
    chapter_id = serializers.PrimaryKeyRelatedField(queryset=Chapter.objects.all(), source='chapter', write_only=True)


    class Meta:
        model = ViewHistory
        fields = ['id', 'user', 'chapter', 'viewed_at', 'user_id', 'chapter_id']
