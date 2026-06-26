from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    User, UserPaymentMethod, Subscription, UserSubscription,
    Genre, Franchise, Chapter, Episode, Person,
    ChapterPersonRole, Comment, Review, Rating,
    Playlist, PlaylistChapter, ViewHistory
)
import csv
from django.http import HttpResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from .subscription_pdf_export import export_subscription_pdf

@admin.action(description="📤 Экспорт выбранных глав в CSV")
def export_chapters_to_csv(modeladmin, request, queryset):
    """Создаёт CSV-файл с детальной информацией о выбранных главах"""
    # 🔥 Важные настройки для русской локализации
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'chapters_export.csv'

    # 🔥 Используем точку с запятой как разделитель (для русского Excel)
    # quoting=csv.QUOTE_MINIMAL — автоматически экранирует кавычки и запятые в данных
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    
    # Заголовки
    writer.writerow([
        'ID', 
        'Название', 
        'Франшиза', 
        'Дата выхода', 
        'Тип контента', 
        'Возрастной рейтинг', 
        'Страна',
        'Средний рейтинг', 
        'Просмотры', 
        'Требуемая подписка'
    ])

    for chapter in queryset:
        # 🔥 Безопасное получение значений с защитой от None
        franchise_name = chapter.franchise.title if chapter.franchise else '—'
        release_date = chapter.release_date.strftime('%Y-%m-%d') if chapter.release_date else '—'
        content_type = chapter.get_content_type_display() if chapter.content_type else '—'
        country = chapter.country or '—'
        subscription = chapter.required_subscription.title if chapter.required_subscription else 'Бесплатно'
        
        writer.writerow([
            chapter.id,
            chapter.title,
            franchise_name,
            release_date,
            content_type,
            chapter.age_rating,
            country,
            chapter.average_rating(),
            chapter.view_count,
            subscription,
        ])

    modeladmin.message_user(
        request, 
        f"✅ Экспортировано {queryset.count()} записей в CSV", 
        level=messages.SUCCESS
    )
    return response

class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0
    verbose_name = _("Эпизод")
    verbose_name_plural = _("Эпизоды")


class ChapterPersonRoleInline(admin.TabularInline):
    model = ChapterPersonRole
    extra = 0
    verbose_name = _("Роль персонажа")
    verbose_name_plural = _("Роли персонажей")


class PlaylistChapterInline(admin.TabularInline):
    model = PlaylistChapter
    extra = 0
    verbose_name = _("Глава плейлиста")
    verbose_name_plural = _("Главы плейлиста")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    filter_horizontal = ('groups', 'user_permissions')
    fieldsets = (
        (_('Личная информация'), {'fields': ('username', 'password')}),
        (_('Персональные данные'), {'fields': ('first_name', 'last_name', 'email', 'profile_pic', 'description')}),
        (_('Разрешения'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Важные даты'), {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ('last_login', 'date_joined')


@admin.register(UserPaymentMethod)
class UserPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('user_display', 'payment_type', 'provider_id', 'masked_card_number')
    list_filter = ('payment_type',)
    search_fields = ('user__username', 'provider_id', 'masked_card_number')
    raw_id_fields = ('user',)

    @admin.display(description="Пользователь")
    def user_display(self, obj):
        return obj.user


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('title_display', 'price_usd', 'duration_days')
    search_fields = ('title',)
    list_filter = ('duration_days',)

    @admin.display(description="Название подписки")
    def title_display(self, obj):
        return obj.title


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    actions = [export_subscription_pdf]
    
    list_display = ('user_display', 'subscription_display', 'start_date', 'end_date', 'is_active', 'auto_renew')
    list_filter = ('is_active', 'auto_renew', 'created_at')
    search_fields = ('user__username', 'subscription__title')
    raw_id_fields = ('user', 'subscription')
    filter_horizontal = ('payment_methods',)
    date_hierarchy = 'start_date'
    readonly_fields = ('created_at', 'updated_at', 'canceled_at')

    @admin.display(description="Пользователь")
    def user_display(self, obj):
        return obj.user

    @admin.display(description="Подписка")
    def subscription_display(self, obj):
        return obj.subscription


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name_display',)
    search_fields = ('name',)

    @admin.display(description="Жанр")
    def name_display(self, obj):
        return obj.name


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ('title_display', 'created_at', 'updated_at', 'chapters_count')
    search_fields = ('title',)
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Название франшизы')
    def title_display(self, obj):
        return obj.title

    @admin.display(description='Количество глав')
    def chapters_count(self, obj):
        return obj.chapters.count()


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    actions = [export_chapters_to_csv] 

    list_display = (
        'title_display', 'franchise', 'release_date',
        'content_type', 'age_rating', 'view_count',
        'average_rating_display', 'reviews_count_display'
    )
    list_filter = ('content_type', 'age_rating', 'release_date')
    search_fields = ('title', 'description', 'country')
    raw_id_fields = ('franchise', 'required_subscription')
    filter_horizontal = ('genres',)
    date_hierarchy = 'release_date'
    inlines = [EpisodeInline, ChapterPersonRoleInline]
    readonly_fields = ('rating_cache', 'view_count')

    @admin.display(description='Название')
    def title_display(self, obj):
        return obj.title

    @admin.display(description='Средний рейтинг')
    def average_rating_display(self, obj):
        return obj.average_rating()

    @admin.display(description='Количество отзывов')
    def reviews_count_display(self, obj):
        return obj.reviews.count()


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('title_display', 'chapter', 'episode_number', 'release_date', 'duration')
    list_filter = ('release_date',)
    search_fields = ('title', 'chapter__title')
    raw_id_fields = ('chapter',)
    date_hierarchy = 'release_date'

    @admin.display(description='Название')
    def title_display(self, obj):
        return obj.title


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'birth_date', 'country')
    search_fields = ('first_name', 'last_name', 'country')
    date_hierarchy = 'birth_date'


@admin.register(ChapterPersonRole)
class ChapterPersonRoleAdmin(admin.ModelAdmin):
    list_display = ('chapter', 'person', 'role')
    list_filter = ('role',)
    search_fields = ('chapter__title', 'person__first_name', 'person__last_name')
    
    # 👇 ЗАМЕНЯЕМ raw_id_fields НА autocomplete_fields
    # Это дает удобный поиск с выпадающим списком прямо на этой же странице!
    autocomplete_fields = ('chapter', 'person')
    
    # Опционально: удобный порядок полей при редактировании
    fieldsets = (
        (None, {
            'fields': ('chapter', 'person', 'role')
        }),
    )
    
    # Сортировка списка для удобства
    ordering = ('-chapter__release_date', 'person__last_name')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'chapter', 'created_at', 'likes_count', 'dislikes_count')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'chapter__title', 'text')
    raw_id_fields = ('user', 'chapter')
    date_hierarchy = 'created_at'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'chapter', 'created_at', 'likes_count', 'dislikes_count')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'chapter__title', 'text')
    raw_id_fields = ('user', 'chapter')
    date_hierarchy = 'created_at'


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'chapter', 'score', 'created_at')
    list_filter = ('score', 'created_at')
    search_fields = ('user__username', 'chapter__title')
    raw_id_fields = ('user', 'chapter')
    date_hierarchy = 'created_at'


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('title_display', 'user', 'is_public', 'is_favorite', 'created_at')
    list_filter = ('is_public', 'is_favorite', 'created_at')
    search_fields = ('title', 'description', 'user__username')
    raw_id_fields = ('user',)
    date_hierarchy = 'created_at'
    inlines = [PlaylistChapterInline]
    readonly_fields = ('slug', 'created_at', 'updated_at')

    @admin.display(description='Название плейлиста')
    def title_display(self, obj):
        return obj.title


@admin.register(PlaylistChapter)
class PlaylistChapterAdmin(admin.ModelAdmin):
    list_display = ('playlist', 'chapter', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('playlist__title', 'chapter__title')
    raw_id_fields = ('playlist', 'chapter')
    date_hierarchy = 'added_at'


@admin.register(ViewHistory)
class ViewHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'chapter', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('user__username', 'chapter__title')
    raw_id_fields = ('user', 'chapter')
    date_hierarchy = 'viewed_at'

from django.contrib import admin
from .models import CompanySettings


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    """Админка для настроек компании"""
    list_display = ['company_name', 'age_rating', 'updated_at', 'updated_by']
    readonly_fields = ['updated_at', 'updated_by']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('company_name', 'copyright_text', 'age_rating')
        }),
        ('Поддержка', {
            'fields': ('support_text', 'support_button_text')
        }),
        ('Социальные сети', {
            'fields': ('social_links',),
            'description': 'Формат: {"vk": "...", "telegram": "...", "youtube": "...", "ok": "..."}'
        }),
        ('Футер', {
            'fields': ('footer_poem',),
            'classes': ('wide',)
        }),
        ('Мета-данные', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Запрещаем создание новых объектов (только один singleton)"""
        return not CompanySettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Запрещаем удаление настроек"""
        return False