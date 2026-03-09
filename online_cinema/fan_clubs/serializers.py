from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import FanClub, FanClubPhoto, FanClubMembership, FanClubApplicationAttachment
from django.utils import timezone

User = get_user_model()

# ==============================================================================
# ФОТО КЛУБА
# ==============================================================================
class FanClubPhotoSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    photo_url = serializers.ImageField(source='photo', read_only=True)

    class Meta:
        model = FanClubPhoto
        fields = ['id', 'photo_url', 'caption', 'uploaded_at', 'uploaded_by_username', 'file_size_mb']
        read_only_fields = ['uploaded_at', 'file_size_mb', 'uploaded_by']

    def get_file_size_mb(self, obj):
        return f"{obj.file_size / 1024 / 1024:.2f} MB" if obj.file_size else None


# ==============================================================================
# ВЛОЖЕНИЯ ЗАЯВКИ
# ==============================================================================
class FanClubApplicationAttachmentSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.SerializerMethodField()
    photo_url = serializers.ImageField(source='photo', read_only=True)
    can_move_to_gallery = serializers.SerializerMethodField()

    class Meta:
        model = FanClubApplicationAttachment
        fields = [
            'id', 'photo_url', 'caption', 'uploaded_at', 'file_size_mb', 
            'moved_to_club_gallery', 'can_move_to_gallery'
        ]
        read_only_fields = ['uploaded_at', 'file_size_mb', 'moved_to_club_gallery']

    def get_file_size_mb(self, obj):
        return f"{obj.file_size / 1024 / 1024:.2f} MB" if obj.file_size else None

    def get_can_move_to_gallery(self, obj):
        return not obj.moved_to_club_gallery and obj.membership.club.can_add_club_photo()


# ==============================================================================
# ЧЛЕНСТВО В КЛУБЕ
# ==============================================================================
class FanClubMembershipSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    club_title = serializers.CharField(source='club.title', read_only=True)
    club_id = serializers.IntegerField(source='club.id', read_only=True)
    application_attachments = FanClubApplicationAttachmentSerializer(many=True, read_only=True)
    photos_count = serializers.IntegerField(source='get_application_photos_count', read_only=True)
    can_add_photos = serializers.BooleanField(source='can_add_more_application_photos', read_only=True)
    is_admin = serializers.BooleanField(source='is_admin', read_only=True)
    is_creator = serializers.BooleanField(source='is_creator', read_only=True)

    class Meta:
        model = FanClubMembership
        fields = [
            'id', 'user_id', 'user_username', 'club_id', 'club_title', 'role', 'status',
            'application_data', 'review_comment', 'joined_at', 'applied_at',
            'application_attachments', 'photos_count', 'can_add_photos', 'is_admin', 'is_creator'
        ]
        read_only_fields = ['status', 'joined_at', 'applied_at', 'review_comment', 'role', 'user']


class FanClubMembershipCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FanClubMembership
        fields = ['club', 'application_data']

    def validate(self, data):
        user = self.context['request'].user
        club = data.get('club')
        
        existing = FanClubMembership.objects.filter(
            user=user, 
            club=club, 
            status__in=['pending', 'approved']
        )
        if existing.exists():
            raise serializers.ValidationError("У вас уже есть заявка или вы участник этого клуба")
        
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['status'] = 'pending'
        validated_data['role'] = 'member'
        return super().create(validated_data)


class FanClubMembershipRoleSerializer(serializers.ModelSerializer):
    """Сериализатор для изменения роли (только для админов)"""
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = FanClubMembership
        fields = ['id', 'user_username', 'role', 'status']
        read_only_fields = ['user_username', 'status']


# ==============================================================================
# ФАН-КЛУБ
# ==============================================================================
class FanClubSerializer(serializers.ModelSerializer):
    cover_photo_url = serializers.ImageField(source='cover_photo', read_only=True)
    photos = FanClubPhotoSerializer(many=True, read_only=True)
    photos_count = serializers.IntegerField(source='get_photos_count', read_only=True)
    can_add_photo = serializers.BooleanField(source='can_add_club_photo', read_only=True)
    members_count = serializers.IntegerField(source='get_members_count', read_only=True)
    admins_count = serializers.IntegerField(source='get_admins_count', read_only=True)
    is_admin = serializers.SerializerMethodField()
    is_creator = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = FanClub
        fields = [
            'id', 'title', 'description', 'cover_photo_url', 'slug', 'created_by_username',
            'franchise', 'chapter', 'requirements_text', 'application_questions',
            'max_application_photos', 'max_club_photos', 'allowed_file_types', 'max_file_size_mb',
            'photos', 'photos_count', 'can_add_photo', 'members_count', 'admins_count',
            'is_admin', 'is_creator', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['slug', 'created_at', 'updated_at', 'created_by']

    def get_is_admin(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.has_admin(request.user)
        return False

    def get_is_creator(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_creator(request.user)
        return False


class FanClubCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FanClub
        fields = [
            'title', 'description', 'cover_photo', 'franchise', 'chapter', 
            'requirements_text', 'application_questions'
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        club = super().create(validated_data)
        
        # Создаём запись о членстве для создателя (администратор)
        FanClubMembership.objects.create(
            user=request.user,
            club=club,
            role='admin',
            status='approved',
            joined_at=timezone.now()
        )
        
        return club