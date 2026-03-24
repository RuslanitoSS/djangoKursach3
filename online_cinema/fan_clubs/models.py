from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

User = get_user_model()

# ==============================================================================
# 1. ФАН-КЛУБ
# ==============================================================================
class FanClub(models.Model):
    title = models.CharField(_('Название'), max_length=255)
    description = models.TextField(_('Описание'))
    
    # Обложка клуба (вместо лого)
    cover_photo = models.ImageField(_('Обложка'), upload_to='fan_club_covers/', blank=True, null=True)
    slug = models.SlugField(_('Слаг'), unique=True, blank=True, null=True)
    
    # Привязка к контенту (из приложения cinema)
    franchise = models.ForeignKey(
        'cinema.Franchise', 
        on_delete=models.CASCADE, 
        related_name='fan_clubs', 
        blank=True, 
        null=True, 
        verbose_name=_('Франшиза')
    )
    chapter = models.ForeignKey(
        'cinema.Chapter', 
        on_delete=models.CASCADE, 
        related_name='fan_clubs', 
        blank=True, 
        null=True, 
        verbose_name=_('Глава')
    )
    
    # Создатель клуба (используем settings.AUTH_USER_MODEL для безопасности связей)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_fan_clubs',
        verbose_name=_('Создатель')
    )
    
    # Настройки вступления
    requirements_text = models.TextField(
        _('Требования для вступления'),
        help_text=_("Описание того, что нужно предоставить для вступления"), 
        blank=True
    )
    application_questions = models.JSONField(
        _('Вопросы заявки'),
        default=list, 
        blank=True, 
        help_text=_("Список вопросов: [{'id': 'q1', 'text': 'Вопрос?'}]")
    )
    
    # Лимиты фото
    max_application_photos = models.PositiveIntegerField(
        _('Макс. фото в заявке'),
        default=3, 
        help_text=_("Макс. фото в заявке")
    )
    max_club_photos = models.PositiveIntegerField(
        _('Макс. фото в галерее'),
        default=20, 
        help_text=_("Макс. фото в галерее клуба")
    )
    allowed_file_types = models.CharField(
        _('Разрешённые типы файлов'),
        max_length=255, 
        default='jpg,jpeg,png', 
        help_text=_("Разрешённые расширения")
    )
    max_file_size_mb = models.PositiveIntegerField(
        _('Макс. размер файла (МБ)'),
        default=5, 
        help_text=_("Макс. размер файла в МБ")
    )
    
    is_active = models.BooleanField(_('Активен'), default=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('fan_club_detail', kwargs={'slug': self.slug})

    def get_photos_count(self):
        return self.photos.count()

    def can_add_club_photo(self):
        return self.get_photos_count() < self.max_club_photos

    def get_admins_count(self):
        return self.memberships.filter(role='admin', status='approved').count()

    def get_members_count(self):
        return self.memberships.filter(status='approved').count()

    def has_admin(self, user):
        """Проверить, является ли пользователь администратором клуба"""
        return self.memberships.filter(user=user, role='admin', status='approved').exists()

    def is_creator(self, user):
        """Проверить, является ли пользователь создателем клуба"""
        return self.created_by == user

    def clean(self):
        super().clean()
        # Валидация размера обложки
        if self.cover_photo and self.cover_photo.size > 10 * 1024 * 1024:  # 10MB
            raise ValidationError({'cover_photo': _("Размер обложки не должен превышать 10MB")})

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Фан-клуб')
        verbose_name_plural = _('Фан-клубы')


# ==============================================================================
# 2. ФОТО ГАЛЕРЕИ КЛУБА (Публичные фото)
# ==============================================================================
class FanClubPhoto(models.Model):
    club = models.ForeignKey(FanClub, on_delete=models.CASCADE, related_name='photos', verbose_name=_('Клуб'))
    photo = models.ImageField(_('Фото'), upload_to='fan_club_gallery/')
    caption = models.CharField(_('Подпись'), max_length=255, blank=True, null=True)
    # Используем settings.AUTH_USER_MODEL для связи
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='uploaded_club_photos',
        verbose_name=_('Загрузил')
    )
    uploaded_at = models.DateTimeField(_('Дата загрузки'), auto_now_add=True)
    file_size = models.PositiveIntegerField(_('Размер файла'), blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.photo:
            self.file_size = self.photo.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Photo for {self.club.title}"

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = _('Фото клуба')
        verbose_name_plural = _('Фото клуба')


# ==============================================================================
# 3. ЗАЯВКА / ЧЛЕНСТВО (с ролями)
# ==============================================================================
class FanClubMembership(models.Model):
    ROLE_CHOICES = [
        ('admin', _('Администратор')),
        ('member', _('Участник')),
    ]

    STATUS_CHOICES = [
        ('pending', _('На проверке')),
        ('approved', _('Участник')),
        ('rejected', _('Отказано')),
        ('banned', _('Заблокирован')),
    ]

    # Используем settings.AUTH_USER_MODEL для связи
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='fan_club_memberships',
        verbose_name=_('Пользователь')
    )
    club = models.ForeignKey(
        FanClub, 
        on_delete=models.CASCADE, 
        related_name='memberships',
        verbose_name=_('Клуб')
    )
    
    role = models.CharField(_('Роль'), max_length=20, choices=ROLE_CHOICES, default='member')
    status = models.CharField(_('Статус'), max_length=20, choices=STATUS_CHOICES, default='pending')
    application_data = models.JSONField(
        _('Данные заявки'),
        default=dict, 
        blank=True, 
        help_text=_("Ответы на вопросы")
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reviewed_memberships',
        verbose_name=_('Проверил')
    )
    review_comment = models.TextField(_('Комментарий проверки'), blank=True, null=True)
    
    joined_at = models.DateTimeField(_('Дата вступления'), blank=True, null=True)
    applied_at = models.DateTimeField(_('Дата заявки'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)

    class Meta:
        unique_together = ['user', 'club']
        ordering = ['-role', '-joined_at', '-applied_at']
        verbose_name = _('Членство в клубе')
        verbose_name_plural = _('Членство в клубах')

    def get_application_photos_count(self):
        return self.application_attachments.count()

    def can_add_more_application_photos(self):
        return self.get_application_photos_count() < self.club.max_application_photos

    def is_admin(self):
        return self.role == 'admin' and self.status == 'approved'

    def is_creator(self):
        return self.club.created_by == self.user

    def clean(self):
        super().clean()
        
        # Проверка: нельзя понизить последнего администратора
        if self.pk:  # Только при обновлении существующей записи
            try:
                old_instance = FanClubMembership.objects.get(pk=self.pk)
                if old_instance.role == 'admin' and self.role == 'member':
                    admins_count = self.club.get_admins_count()
                    if admins_count <= 1:
                        raise ValidationError(_("Нельзя понизить последнего администратора клуба"))
            except FanClubMembership.DoesNotExist:
                pass
        
        # Проверка: администратор должен быть утверждённым участником
        if self.role == 'admin' and self.status not in ['approved']:
            raise ValidationError(_("Только утверждённые участники могут быть администраторами"))

    def approve(self, moderator):
        """Одобрить заявку"""
        # Если это первая заявка в клубе - делаем создателем и админом
        is_first_member = self.club.memberships.filter(status='approved').count() == 0
        
        self.status = 'approved'
        self.reviewed_by = moderator
        self.joined_at = timezone.now()
        
        # Первый участник автоматически становится администратором
        if is_first_member:
            self.role = 'admin'
        
        self.save()
        self.delete_application_photos()

    def reject(self, moderator, comment: str):
        """Отклонить заявку"""
        self.status = 'rejected'
        self.reviewed_by = moderator
        self.review_comment = comment
        self.joined_at = None
        self.save()
        self.delete_application_photos()

    def delete_application_photos(self):
        """Удалить все вложения заявки"""
        for attachment in self.application_attachments.all():
            if attachment.photo:
                attachment.photo.delete()
            attachment.delete()

    def promote_to_admin(self, moderator):
        """Повысить до администратора"""
        if not moderator.fan_club_memberships.filter(club=self.club, role='admin', status='approved').exists():
            raise ValidationError(_("Только администратор может назначать других администраторов"))
        
        self.role = 'admin'
        self.save()

    def demote_to_member(self, moderator):
        """Понизить до участника"""
        if not moderator.fan_club_memberships.filter(club=self.club, role='admin', status='approved').exists():
            raise ValidationError(_("Только администратор может понижать администраторов"))
        
        # Проверка: не последний ли админ
        if self.club.get_admins_count() <= 1:
            raise ValidationError(_("Нельзя понизить последнего администратора клуба"))
        
        self.role = 'member'
        self.save()

    def __str__(self):
        return f"{self.user.username} in {self.club.title} ({self.get_role_display()}, {self.get_status_display()})"


# ==============================================================================
# 4. ВЛОЖЕНИЯ К ЗАЯВКЕ (Фото на проверку)
# ==============================================================================
class FanClubApplicationAttachment(models.Model):
    membership = models.ForeignKey(
        FanClubMembership, 
        on_delete=models.CASCADE, 
        related_name='application_attachments',
        verbose_name=_('Членство')
    )
    photo = models.ImageField(_('Фото'), upload_to='fan_club_applications/')
    caption = models.CharField(_('Подпись'), max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(_('Дата загрузки'), auto_now_add=True)
    file_size = models.PositiveIntegerField(_('Размер файла'), blank=True, null=True)
    
    # Флаг: перенесено ли фото в галерею клуба
    moved_to_club_gallery = models.BooleanField(_('Перенесено в галерею'), default=False)
    club_photo = models.ForeignKey(
        FanClubPhoto, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='source_attachments',
        verbose_name=_('Фото в галерее')
    )

    def save(self, *args, **kwargs):
        if self.photo:
            self.file_size = self.photo.size
        super().save(*args, **kwargs)

    def move_to_club_gallery(self, caption=None, uploaded_by=None):
        """Перенести фото из заявки в галерею клуба"""
        if self.moved_to_club_gallery:
            raise ValidationError(_("Фото уже перенесено в галерею"))
        
        if not self.membership.club.can_add_club_photo():
            raise ValidationError(_("Достигнут лимит фото в галерее клуба"))
        
        # Создаём копию в галерее
        club_photo = FanClubPhoto.objects.create(
            club=self.membership.club,
            photo=self.photo,
            caption=caption or self.caption,
            uploaded_by=uploaded_by or self.membership.reviewed_by
        )
        
        self.moved_to_club_gallery = True
        self.club_photo = club_photo
        self.save()
        
        return club_photo

    def __str__(self):
        return f"Attachment for {self.membership.user.username} in {self.membership.club.title}"

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = _('Вложение заявки')
        verbose_name_plural = _('Вложения заявок')