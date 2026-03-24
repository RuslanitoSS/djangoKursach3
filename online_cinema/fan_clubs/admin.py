from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    FanClub, 
    FanClubPhoto, 
    FanClubMembership, 
    FanClubApplicationAttachment
)

# ==============================================================================
# ИНЛАЙНЫ (Встроенные модели)
# ==============================================================================

class FanClubPhotoInline(admin.TabularInline):
    model = FanClubPhoto
    extra = 0
    verbose_name = _('Фото клуба')
    verbose_name_plural = _('Фото клуба')
    readonly_fields = ('uploaded_at', 'file_size')
    # raw_id_fields не нужен для inline, если фото не тысячи, но можно добавить при необходимости
    # raw_id_fields = ('uploaded_by',)

class FanClubMembershipInline(admin.TabularInline):
    model = FanClubMembership
    extra = 0
    verbose_name = _('Членство')
    verbose_name_plural = _('Членства')
    readonly_fields = ('applied_at', 'joined_at', 'updated_at')
    raw_id_fields = ('user', 'reviewed_by')

# ==============================================================================
# 1. ФАН-КЛУБ
# ==============================================================================

@admin.register(FanClub)
class FanClubAdmin(admin.ModelAdmin):
    # ✅ list_display: основные поля для отображения
    list_display = (
        'title', 
        'franchise', 
        'chapter', 
        'created_by', 
        'get_members_count', 
        'is_active',
        'created_at'
    )
    
    # ✅ list_filter: фильтры справа (включая связанные модели)
    list_filter = (
        'is_active', 
        'franchise', 
        'chapter', 
        'created_at',
        'created_by'
    )
    
    # ✅ search_fields: поиск по полям связанных моделей (через __)
    search_fields = (
        'title', 
        'description', 
        'franchise__title', 
        'chapter__title', 
        'created_by__username',
        'created_by__email'
    )
    
    # ✅ raw_id_fields: обязательно для ForeignKey на User и большие таблицы
    # Предотвращает загрузку выпадающего списка со всеми пользователями/франшизами
    raw_id_fields = ('franchise', 'chapter', 'created_by')
    
    # ✅ readonly_fields: поля, которые нельзя редактировать вручную
    readonly_fields = ('slug', 'created_at', 'updated_at', 'slug')
    
    # ✅ filter_horizontal: удобный виджет для ManyToMany (если бы были в этой модели)
    # filter_horizontal = ('some_m2m_field',)
    
    # ✅ Inlines: отображение связанных объектов внутри страницы клуба
    inlines = [FanClubPhotoInline, FanClubMembershipInline]
    
    # ✅ fieldsets: группировка полей на странице редактирования
    fieldsets = (
        (_('Основная информация'), {
            'fields': ('title', 'description', 'cover_photo', 'slug')
        }),
        (_('Привязка к контенту'), {
            'fields': ('franchise', 'chapter')
        }),
        (_('Создатель и настройки'), {
            'fields': ('created_by', 'is_active')
        }),
        (_('Требования и заявки'), {
            'fields': ('requirements_text', 'application_questions')
        }),
        (_('Лимиты файлов'), {
            'fields': (
                'max_application_photos', 
                'max_club_photos', 
                'allowed_file_types', 
                'max_file_size_mb'
            )
        }),
        (_('Даты'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# ==============================================================================
# 2. ФОТО ГАЛЕРЕИ КЛУБА
# ==============================================================================

@admin.register(FanClubPhoto)
class FanClubPhotoAdmin(admin.ModelAdmin):
    list_display = ('photo_preview', 'club', 'caption', 'uploaded_by', 'uploaded_at', 'file_size')
    list_filter = ('uploaded_at', 'club', 'uploaded_by')
    search_fields = ('caption', 'club__title', 'uploaded_by__username')
    raw_id_fields = ('club', 'uploaded_by')  # ✅ Важно для больших баз
    readonly_fields = ('uploaded_at', 'file_size', 'photo_preview')
    date_hierarchy = 'uploaded_at'

    @admin.display(description=_('Фото'))
    def photo_preview(self, obj):
        if obj.photo:
            return f"📷 {obj.photo.name.split('/')[-1]}"
        return _('Нет фото')

# ==============================================================================
# 3. ЧЛЕНСТВО / ЗАЯВКИ
# ==============================================================================

@admin.register(FanClubMembership)
class FanClubMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'club', 'club_franchise', 'role', 'status', 'applied_at', 'reviewed_by')
    list_filter = ('status', 'role', 'club', 'applied_at', 'reviewed_by')
    search_fields = (
        'user__username', 
        'user__email',
        'club__title', 
        'club__franchise__title', 
        'club__chapter__title'
    )
    raw_id_fields = ('user', 'club', 'reviewed_by')  # ✅ Обязательно
    readonly_fields = ('applied_at', 'updated_at', 'joined_at')
    date_hierarchy = 'applied_at'
    
    # ✅ Actions: массовые действия
    actions = ['approve_memberships', 'reject_memberships']

    @admin.display(description=_('Франшиза'))
    def club_franchise(self, obj):
        return obj.club.franchise if obj.club else '-'

    @admin.action(description=_('Одобрить выбранные заявки'))
    def approve_memberships(self, request, queryset):
        # Упрощённая логика для админки
        queryset.update(status='approved')
        
    @admin.action(description=_('Отклонить выбранные заявки'))
    def reject_memberships(self, request, queryset):
        queryset.update(status='rejected')

# ==============================================================================
# 4. ВЛОЖЕНИЯ К ЗАЯВКЕ (ФОТО НА ПРОВЕРКУ)
# ==============================================================================

@admin.register(FanClubApplicationAttachment)
class FanClubApplicationAttachmentAdmin(admin.ModelAdmin):
    list_display = ('membership', 'photo_preview', 'caption', 'moved_to_club_gallery', 'uploaded_at')
    list_filter = ('moved_to_club_gallery', 'uploaded_at', 'membership__club')
    search_fields = (
        'caption', 
        'membership__user__username', 
        'membership__club__title'
    )
    raw_id_fields = ('membership', 'club_photo')  # ✅ Обязательно
    readonly_fields = ('uploaded_at', 'file_size', 'photo_preview', 'moved_to_club_gallery')
    date_hierarchy = 'uploaded_at'

    @admin.display(description=_('Фото'))
    def photo_preview(self, obj):
        if obj.photo:
            return f"📎 {obj.photo.name.split('/')[-1]}"
        return _('Нет фото')