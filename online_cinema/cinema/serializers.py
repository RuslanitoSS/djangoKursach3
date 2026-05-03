from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import (
    Chapter, ChapterPersonRole, Comment, Episode, Franchise, Genre,
    Person, Playlist, PlaylistChapter, Rating, Review, Subscription,
    User, UserPaymentMethod, UserSubscription, ViewHistory
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    profile_pic_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile_pic_url', 'description', 'login_code', 'groups', 'user_permissions']
        extra_kwargs = {
            'login_code': {'write_only': True},
            'groups': {'required': False},
            'user_permissions': {'required': False}
        }

    def get_profile_pic_url(self, obj):
        if not obj.profile_pic:
            return None
        url = obj.profile_pic.url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


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


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ['id', 'first_name', 'last_name', 'birth_date', 'country', 'photo_url', 'biography']


class FranchiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Franchise
        fields = ['id', 'title', 'created_at', 'updated_at']


class EpisodeSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField(read_only=True)
    thumbnail_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Episode
        fields = ['id', 'chapter', 'episode_number', 'title', 'video_url', 'duration', 'release_date', 'thumbnail_url']
        extra_kwargs = {
            'chapter': {'required': False},
        }

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


class ChapterSerializer(serializers.ModelSerializer):
    franchise = FranchiseSerializer(read_only=True)
    required_subscription = SubscriptionSerializer(read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    people = PersonSerializer(many=True, read_only=True)
    poster_img_url = serializers.SerializerMethodField(read_only=True)
    franchise_overview = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = ['id', 'poster_img_url', 'title', 'release_date', 'rating_cache', 'view_count', 'franchise', 'required_subscription', 'genres', 'people', 'franchise_overview']

    def get_poster_img_url(self, obj):
        if obj.poster_image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.poster_image.url) if request else obj.poster_image.url
        return None

    def get_franchise_overview(self, obj):
        if obj.franchise and hasattr(obj.franchise, 'get_chapter_overview'):
            return obj.franchise.get_chapter_overview()
        return []


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