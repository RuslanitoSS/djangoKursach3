from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
import os

User = get_user_model()

# ==============================================================================
# УТИЛИТЫ ВАЛИДАЦИИ
# ==============================================================================
def validate_image_file(file_obj, max_size_mb=10, allowed_types=None):
    """
    Универсальная валидация изображения.
    
    Args:
        file_obj: файл для проверки
        max_size_mb: максимальный размер в МБ
        allowed_types: список разрешённых расширений (например, ['jpg', 'jpeg', 'png'])
    """
    if not file_obj:
        return
    
    # Проверка размера
    max_bytes = max_size_mb * 1024 * 1024
    if file_obj.size > max_bytes:
        raise ValidationError(
            _(f"Размер файла не должен превышать {max_size_mb} МБ "
              f"(получено {file_obj.size / 1024 / 1024:.2f} МБ)")
        )
    
    # Проверка типа файла
    if allowed_types:
        ext = os.path.splitext(file_obj.name)[1].lower().lstrip('.')
        if ext not in [t.lower() for t in allowed_types]:
            raise ValidationError(
                _(f"Недопустимый формат файла: .{ext}. "
                  f"Разрешены: {', '.join(allowed_types)}")
            )
    
    # Проверка MIME-типа (защита от подмены расширения)
    allowed_mime = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
    }
    
    if hasattr(file_obj, 'content_type'):
        if file_obj.content_type not in allowed_mime.values():
            raise ValidationError(
                _("Недопустимый тип файла. Разрешены только изображения.")
            )


# ==============================================================================
# 1. ФАН-КЛУБ
# ==============================================================================
class FanClub(models.Model):
    title = models.CharField(_('Название'), max_length=255)
    description = models.TextField(_('Описание'))
    
    cover_photo = models.ImageField(_('Обложка'), upload_to='fan_club_covers/', blank=True, null=True)
    slug = models.SlugField(_('Слаг'), unique=True, blank=True, null=True)
    
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
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_fan_clubs',
        verbose_name=_('Создатель')
    )
    
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
    
    # 👇 Добавлены ограничения через validators
    max_application_photos = models.PositiveIntegerField(
        _('Макс. фото в заявке'),
        default=3,
    )
    max_club_photos = models.PositiveIntegerField(
        _('Макс. фото в галерее'),
        default=20,
    )
    allowed_file_types = models.CharField(
        _('Разрешённые типы файлов'),
        max_length=255, 
        default='jpg,jpeg,png', 
    )
    max_file_size_mb = models.PositiveIntegerField(
        _('Макс. размер файла (МБ)'),
        default=5,
    )
    
    is_active = models.BooleanField(_('Активен'), default=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            # 👇 Защита от дубликатов slug
            while FanClub.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
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
        return self.memberships.filter(user=user, role='admin', status='approved').exists()

    def is_creator(self, user):
        return self.created_by == user

    def get_allowed_file_types_list(self):
        """Возвращает список разрешённых расширений"""
        return [t.strip().lower() for t in self.allowed_file_types.split(',') if t.strip()]

    def clean(self):
        super().clean()
        errors = {}
        
        # 👇 Валидация размера обложки
        if self.cover_photo:
            try:
                validate_image_file(
                    self.cover_photo, 
                    max_size_mb=10,
                    allowed_types=['jpg', 'jpeg', 'png']
                )
            except ValidationError as e:
                errors['cover_photo'] = e.messages
        
        # 👇 Валидация названия
        if self.title and len(self.title.strip()) < 3:
            errors['title'] = _("Название должно содержать минимум 3 символа")
        
        # 👇 Валидация описания
        if self.description and len(self.description.strip()) < 10:
            errors['description'] = _("Описание должно содержать минимум 10 символов")
        
        # 👇 Валидация лимитов (разумные пределы)
        if self.max_application_photos < 1 or self.max_application_photos > 20:
            errors['max_application_photos'] = _("Допустимо от 1 до 20 фото в заявке")
        
        if self.max_club_photos < 1 or self.max_club_photos > 200:
            errors['max_club_photos'] = _("Допустимо от 1 до 200 фото в галерее")
        
        if self.max_file_size_mb < 1 or self.max_file_size_mb > 50:
            errors['max_file_size_mb'] = _("Допустимо от 1 до 50 МБ")
        
        # 👇 Валидация allowed_file_types
        allowed = self.get_allowed_file_types_list()
        valid_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        invalid = [ext for ext in allowed if ext not in valid_extensions]
        if invalid:
            errors['allowed_file_types'] = _(
                f"Недопустимые расширения: {', '.join(invalid)}. "
                f"Разрешены: {', '.join(valid_extensions)}"
            )
        
        # 👇 Валидация структуры application_questions
        if self.application_questions:
            if not isinstance(self.application_questions, list):
                errors['application_questions'] = _("Должен быть список вопросов")
            else:
                for i, q in enumerate(self.application_questions):
                    if not isinstance(q, dict):
                        errors['application_questions'] = _(
                            f"Вопрос #{i+1} должен быть объектом"
                        )
                        break
                    if 'text' not in q or not q['text'].strip():
                        errors['application_questions'] = _(
                            f"Вопрос #{i+1} должен содержать текст"
                        )
                        break
        
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Фан-клуб')
        verbose_name_plural = _('Фан-клубы')


# ==============================================================================
# 2. ФОТО ГАЛЕРЕИ КЛУБА
# ==============================================================================
class FanClubPhoto(models.Model):
    club = models.ForeignKey(FanClub, on_delete=models.CASCADE, related_name='photos', verbose_name=_('Клуб'))
    photo = models.ImageField(_('Фото'), upload_to='fan_club_gallery/')
    caption = models.CharField(_('Подпись'), max_length=255, blank=True, null=True)
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

    def clean(self):
        super().clean()
        if self.photo:
            # 👇 Валидация размера и типа фото
            max_size = self.club.max_file_size_mb if self.club else 5
            allowed_types = self.club.get_allowed_file_types_list() if self.club else ['jpg', 'jpeg', 'png']
            validate_image_file(self.photo, max_size_mb=max_size, allowed_types=allowed_types)
            
            # 👇 Проверка лимита фото в галерее
            if self.club and self.pk is None:  # Только при создании
                if not self.club.can_add_club_photo():
                    raise ValidationError(
                        _("Достигнут лимит фото в галерее клуба")
                    )

    def __str__(self):
        return f"Photo for {self.club.title}"

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = _('Фото клуба')
        verbose_name_plural = _('Фото клуба')


# ==============================================================================
# 3. ЗАЯВКА / ЧЛЕНСТВО
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
        errors = {}
        
        # 👇 Проверка: нельзя понизить последнего администратора
        if self.pk:
            try:
                old_instance = FanClubMembership.objects.get(pk=self.pk)
                if old_instance.role == 'admin' and self.role == 'member':
                    admins_count = self.club.get_admins_count()
                    if admins_count <= 1:
                        errors['role'] = _("Нельзя понизить последнего администратора клуба")
            except FanClubMembership.DoesNotExist:
                pass
        
        # 👇 Проверка: администратор должен быть утверждённым
        if self.role == 'admin' and self.status not in ['approved']:
            errors['role'] = _("Только утверждённые участники могут быть администраторами")
        
        # 👇 Проверка: нельзя заблокировать самого себя (если последний админ)
        if self.status == 'banned' and self.role == 'admin':
            if self.club.get_admins_count() <= 1:
                errors['status'] = _("Нельзя заблокировать последнего администратора")
        
        # 👇 Валидация application_data
        if self.application_data and self.club.application_questions:
            if not isinstance(self.application_data, dict):
                errors['application_data'] = _("Данные заявки должны быть объектом")
        
        if errors:
            raise ValidationError(errors)

    def approve(self, moderator):
        is_first_member = self.club.memberships.filter(status='approved').count() == 0
        
        self.status = 'approved'
        self.reviewed_by = moderator
        self.joined_at = timezone.now()
        
        if is_first_member:
            self.role = 'admin'
        
        self.save()
        self.delete_application_photos()

    def reject(self, moderator, comment: str):
        self.status = 'rejected'
        self.reviewed_by = moderator
        self.review_comment = comment
        self.joined_at = None
        self.save()
        self.delete_application_photos()

    def delete_application_photos(self):
        for attachment in self.application_attachments.all():
            if attachment.photo:
                attachment.photo.delete()
            attachment.delete()

    def promote_to_admin(self, moderator):
        if not moderator.fan_club_memberships.filter(
            club=self.club, role='admin', status='approved'
        ).exists():
            raise ValidationError(_("Только администратор может назначать других администраторов"))
        
        self.role = 'admin'
        self.save()

    def demote_to_member(self, moderator):
        if not moderator.fan_club_memberships.filter(
            club=self.club, role='admin', status='approved'
        ).exists():
            raise ValidationError(_("Только администратор может понижать администраторов"))
        
        if self.club.get_admins_count() <= 1:
            raise ValidationError(_("Нельзя понизить последнего администратора клуба"))
        
        self.role = 'member'
        self.save()

    def __str__(self):
        return f"{self.user.username} in {self.club.title} ({self.get_role_display()}, {self.get_status_display()})"


# ==============================================================================
# 4. ВЛОЖЕНИЯ К ЗАЯВКЕ
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

    def clean(self):
        super().clean()
        if self.photo:
            # 👇 Валидация размера и типа
            max_size = self.membership.club.max_file_size_mb if self.membership.club else 5
            allowed_types = (
                self.membership.club.get_allowed_file_types_list() 
                if self.membership.club else ['jpg', 'jpeg', 'png']
            )
            validate_image_file(self.photo, max_size_mb=max_size, allowed_types=allowed_types)
            
            # 👇 Проверка лимита фото в заявке
            if self.membership and self.pk is None:
                if not self.membership.can_add_more_application_photos():
                    raise ValidationError(
                        _("Достигнут лимит фото в заявке")
                    )
            
            # 👇 Заявка должна быть в статусе pending
            if self.membership and self.membership.status != 'pending':
                raise ValidationError(
                    _("Нельзя добавлять фото к обработанной заявке")
                )

    def move_to_club_gallery(self, caption=None, uploaded_by=None):
        if self.moved_to_club_gallery:
            raise ValidationError(_("Фото уже перенесено в галерею"))
        
        if not self.membership.club.can_add_club_photo():
            raise ValidationError(_("Достигнут лимит фото в галерее клуба"))
        
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