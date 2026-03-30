from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import FanClub, FanClubPhoto, FanClubMembership, FanClubApplicationAttachment


class FanClubPhotoInline(admin.TabularInline):
    model = FanClubPhoto
    extra = 1
    fields = ['photo_preview', 'caption', 'uploaded_by', 'uploaded_at']
    readonly_fields = ['photo_preview', 'uploaded_by', 'uploaded_at']

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height: 100px; border-radius: 5px;" />', obj.photo.url)
        return "Нет фото"
    photo_preview.short_description = 'Предпросмотр'


class FanClubApplicationAttachmentInline(admin.TabularInline):
    model = FanClubApplicationAttachment
    extra = 0
    fields = ['photo_preview', 'caption', 'file_size', 'uploaded_at', 'moved_to_club_gallery', 'club_photo']
    readonly_fields = ['photo_preview', 'file_size', 'uploaded_at', 'moved_to_club_gallery', 'club_photo']
    can_delete = False

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height: 100px; border-radius: 5px;" />', obj.photo.url)
        return "Нет фото"
    photo_preview.short_description = 'Предпросмотр'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FanClub)
class FanClubAdmin(admin.ModelAdmin):
    list_display = ['title', 'cover_preview', 'slug', 'is_active', 'created_at', 'get_admins_count', 'get_members_count']
    list_filter = ['is_active', 'created_at', 'franchise', 'chapter']
    search_fields = ['title', 'description']
    inlines = [FanClubPhotoInline]
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    fieldsets = (
        ('Основное', {'fields': ['title', 'description', 'slug', 'cover_photo']}),
        ('Привязка', {'fields': ['franchise', 'chapter', 'created_by']}),
        ('Настройки', {'fields': ['requirements_text', 'application_questions']}),
        ('Лимиты', {'fields': ['max_application_photos', 'max_club_photos', 'allowed_file_types', 'max_file_size_mb']}),
        ('Статус', {'fields': ['is_active', 'created_at', 'updated_at']}),
    )

    def cover_preview(self, obj):
        if obj.cover_photo:
            return format_html('<img src="{}" style="max-height: 50px; border-radius: 5px;" />', obj.cover_photo.url)
        return "Нет обложки"
    cover_preview.short_description = 'Обложка'

    def get_admins_count(self, obj):
        return obj.get_admins_count()
    get_admins_count.short_description = 'Админов'

    def get_members_count(self, obj):
        return obj.get_members_count()
    get_members_count.short_description = 'Участников'


@admin.register(FanClubPhoto)
class FanClubPhotoAdmin(admin.ModelAdmin):
    list_display = ['club', 'photo_preview', 'caption', 'uploaded_at', 'file_size']
    list_filter = ['club', 'uploaded_at']
    search_fields = ['club__title', 'caption']
    readonly_fields = ['photo_preview', 'file_size', 'uploaded_at']

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height: 50px; border-radius: 5px;" />', obj.photo.url)
        return "Нет фото"
    photo_preview.short_description = 'Фото'


@admin.register(FanClubMembership)
class FanClubMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'club', 'role_badge', 'status_badge', 'applied_at', 'joined_at']
    list_filter = ['role', 'status', 'club', 'applied_at']
    search_fields = ['user__username', 'club__title']
    inlines = [FanClubApplicationAttachmentInline]
    readonly_fields = ['applied_at', 'updated_at', 'joined_at', 'reviewed_by']
    
    fieldsets = (
        ('Информация', {'fields': ['user', 'club', 'role', 'status']}),
        ('Данные заявки', {'fields': ['application_data']}),
        ('Модерация', {'fields': ['reviewed_by', 'review_comment', 'joined_at']}),
        ('Даты', {'fields': ['applied_at', 'updated_at'], 'classes': ['collapse']}),
    )

    actions = ['approve_memberships', 'reject_memberships', 'promote_to_admin', 'demote_to_member']

    def role_badge(self, obj):
        if obj.role == 'admin':
            return format_html('<span style="color: green; font-weight: bold;">👑 Администратор</span>')
        return '<span style="color: blue;">👤 Участник</span>'
    role_badge.short_description = 'Роль'

    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
            'banned': 'gray'
        }
        return format_html(f'<span style="color: {colors.get(obj.status, "black")}; font-weight: bold;">{obj.get_status_display()}</span>')
    status_badge.short_description = 'Статус'

    @admin.action(description='✅ Одобрить выбранные заявки')
    def approve_memberships(self, request, queryset):
        count = queryset.filter(status='pending').count()
        for membership in queryset.filter(status='pending'):
            membership.approve(request.user)
        self.message_user(request, f"Одобрено {count} заявок")

    @admin.action(description='❌ Отклонить выбранные заявки')
    def reject_memberships(self, request, queryset):
        count = queryset.filter(status='pending').count()
        for membership in queryset.filter(status='pending'):
            membership.reject(request.user, "Отклонено администратором")
        self.message_user(request, f"Отклонено {count} заявок")

    @admin.action(description='👑 Повысить до администратора')
    def promote_to_admin(self, request, queryset):
        success = 0
        for membership in queryset.filter(status='approved', role='member'):
            try:
                membership.promote_to_admin(request.user)
                success += 1
            except Exception:
                pass
        self.message_user(request, f"Повышено {success} участников")

    @admin.action(description='👤 Понизить до участника')
    def demote_to_member(self, request, queryset):
        success = 0
        for membership in queryset.filter(status='approved', role='admin'):
            try:
                membership.demote_to_member(request.user)
                success += 1
            except Exception:
                pass
        self.message_user(request, f"Понижено {success} администраторов")


@admin.register(FanClubApplicationAttachment)
class FanClubApplicationAttachmentAdmin(admin.ModelAdmin):
    list_display = ['membership', 'photo_preview', 'caption', 'uploaded_at', 'moved_to_club_gallery']
    list_filter = ['moved_to_club_gallery', 'uploaded_at', 'membership__club']
    readonly_fields = ['photo_preview', 'file_size', 'uploaded_at']
    search_fields = ['membership__user__username', 'membership__club__title']

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height: 50px; border-radius: 5px;" />', obj.photo.url)
        return "Нет фото"
    photo_preview.short_description = 'Фото'

    actions = ['move_to_gallery']

    @admin.action(description='📁 Перенести выбранные фото в галерею клуба')
    def move_to_gallery(self, request, queryset):
        success = 0
        errors = 0
        for attachment in queryset.filter(moved_to_club_gallery=False):
            try:
                attachment.move_to_club_gallery(uploaded_by=request.user)
                success += 1
            except Exception:
                errors += 1
        self.message_user(request, f"Перенесено: {success}, Ошибок: {errors}")