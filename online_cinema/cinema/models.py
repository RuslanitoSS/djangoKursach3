import re
import datetime
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Avg



# Пользователь
class User(AbstractUser):
    profile_pic = models.ImageField(_('Фото профиля'), upload_to='user_profile_pics/', blank=True, null=True)
    description = models.TextField(_('Описание'), blank=True, null=True)
    login_code = models.CharField(_('Код входа'), max_length=255, blank=True, null=True)  # поле для входа по коду

    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
        help_text=_('Группы, к которым принадлежит этот пользователь.'),
        verbose_name=_('группы'),
    )

    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_set',
        blank=True,
        help_text=_('Специфические права для этого пользователя.'),
        verbose_name=_('права пользователя'),
    )

    def get_absolute_url(self):
        return reverse('user_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = _('Пользователь')
        verbose_name_plural = _('Пользователи')


# 1. UserPaymentMethod
class UserPaymentMethod(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('card', _('Банковская карта')),
        ('paypal', 'PayPal'),
        ('apple_pay', 'Apple Pay'),
        ('google_pay', 'Google Pay'),
        ('yoo_money', 'ЮMoney'),
        ('sbp', 'СБП'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods', verbose_name=_('Пользователь'))
    payment_type = models.CharField(_('Тип оплаты'), max_length=20, choices=PAYMENT_TYPE_CHOICES)
    provider_id = models.CharField(_('ID провайдера'), max_length=255)
    masked_card_number = models.CharField(_('Маска номера карты'), max_length=19, blank=True, null=True)
    card_brand = models.CharField(_('Платежная система'), max_length=50, blank=True, null=True)
    card_expiry_month = models.IntegerField(_('Месяц истечения'), blank=True, null=True)
    card_expiry_year = models.IntegerField(_('Год истечения'), blank=True, null=True)
    added_at = models.DateTimeField(_('Добавлено'), auto_now_add=True)
    valid_until = models.DateTimeField(_('Действительно до'), blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.added_at:
            self.added_at = timezone.now()
        self.valid_until = self.added_at + datetime.timedelta(days=5*365)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.get_payment_type_display()}"

    class Meta:
        verbose_name = _('Способ оплаты')
        verbose_name_plural = _('Способы оплаты')


# 2. Subscription
class Subscription(models.Model):
    title = models.CharField(_('Название'), max_length=255)
    price_usd = models.DecimalField(_('Цена (USD)'), max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(_('Длительность (дни)'))
    description = models.TextField(_('Описание'))

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('Подписка')
        verbose_name_plural = _('Подписки')


class UserSubscriptionManager(models.Manager):
    def active(self):
        now = timezone.now()
        return self.filter(is_active=True, start_date__lte=now, end_date__gte=now)

    def expired(self):
        now = timezone.now()
        return self.exclude(expiration_date__lt=now)
    
# 3. UserSubscription
class UserSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions', verbose_name=_('Пользователь'))
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='user_subscriptions', verbose_name=_('Тип подписки'))
    start_date = models.DateTimeField(_('Дата начала'))
    end_date = models.DateTimeField(_('Дата окончания'))
    is_active = models.BooleanField(_('Активна'), default=True)
    payment_methods = models.ManyToManyField(UserPaymentMethod, related_name='subscriptions', verbose_name=_('Способы оплаты'))
    auto_renew = models.BooleanField(_('Автопродление'), default=False)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    canceled_at = models.DateTimeField(_('Дата отмены'), blank=True, null=True)

    objects = UserSubscriptionManager()

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + datetime.timedelta(days=self.subscription.duration_days)
        super().save(*args, **kwargs)

    def is_currently_active(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date
    
    def __str__(self):
        return f"{self.user.username} - {self.subscription.title}"

    class Meta:
        verbose_name = _('Подписка пользователя')
        verbose_name_plural = _('Подписки пользователей')


# Жанры
class Genre(models.Model):
    name = models.CharField(_('Название'), max_length=255, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Жанр')
        verbose_name_plural = _('Жанры')


# Франшиза
class Franchise(models.Model):
    title = models.CharField(_('Название'), max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)

    def chapters_count(self):
        return self.chapters.count()

    def get_chapter_overview(self):
        return list(
            self.chapters.values(
                'id', 'chapter_number', 'franchise_relation'
            ).order_by('chapter_number')
        )

    def __str__(self):
        return self.title or _("Без названия")

    class Meta:
        verbose_name = _('Франшиза')
        verbose_name_plural = _('Франшизы')


# Глава
class Chapter(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('movie', _('Фильм')),
        ('series', _('Сериал')),
    ]
    FRANCHISE_RELATION_CHOICES = [
        ('main', _('Основная история')),
        ('spinoff', _('Спин-офф')),
        ('side', _('Побочная история')),
        ('other', _('Другое')),
    ]

    franchise_relation = models.CharField(
        _('Связь с франшизой'),
        max_length=20,
        choices=FRANCHISE_RELATION_CHOICES,
        blank=True,
        null=True,
        help_text=_("Тип связи главы с франшизой (например, основная история, спин-офф и т.д.)")
    )
    franchise = models.ForeignKey(Franchise, related_name='chapters', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Франшиза'))
    title = models.CharField(_('Название'), max_length=255, blank=True, null=True)
    description = models.TextField(_('Описание'), blank=True, null=True)
    release_date = models.DateField(_('Дата выхода'), blank=True, null=True)
    required_subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Требуемая подписка'))
    chapter_number = models.PositiveIntegerField(_('Номер главы'), blank=True, null=True)
    country = models.CharField(_('Страна'), max_length=255, blank=True, null=True)
    age_rating = models.PositiveIntegerField(_('Возрастной рейтинг'), blank=True, null=True)
    content_type = models.CharField(_('Тип контента'), max_length=20, choices=CONTENT_TYPE_CHOICES, blank=True, null=True)
    rating_cache = models.FloatField(_('Кэш рейтинга'), default=0.0)
    view_count = models.PositiveIntegerField(_('Количество просмотров'), default=0)
    poster_image = models.ImageField(_('Постер'), upload_to='chapter_posters/', blank=True, null=True)
    trailer_url = models.URLField(_('Ссылка на трейлер'), blank=True, null=True) 
    
    genres = models.ManyToManyField(Genre, related_name='chapters', blank=True, verbose_name=_('Жанры'))
    people = models.ManyToManyField('Person', through='ChapterPersonRole', related_name='chapters', blank=True, verbose_name=_('Персоны'))

    def episode_count(self):
        return self.episodes.count()

    def get_absolute_url(self):
        return reverse('chapter_detail', kwargs={'pk': self.pk})

    def average_rating(self):
        return self.ratings.aggregate(avg=Avg('score'))['avg'] or 0

    def reviews_count(self):
        return self.reviews.count()

    def clean(self):
        super().clean()
        required_fields = {
            'title': self.title,
            'release_date': self.release_date,
            'content_type': self.content_type,
            'age_rating': self.age_rating,
        }
        # Простая проверка на наличие (для verbose_name в ошибках можно оставить ключи на английском или мапить)
        for field_name, value in required_fields.items():
            if not value:
                # Здесь лучше использовать gettext для сообщения об ошибке, если нужно
                raise ValidationError({field_name: f"Поле обязательно для заполнения."})

        if self.release_date and self.release_date > datetime.date.today():
            raise ValidationError({'release_date': _("Дата релиза не может быть в будущем.")})

        if self.age_rating and not (0 <= self.age_rating <= 21):
            raise ValidationError({'age_rating': _("Возрастной рейтинг должен быть от 0 до 21.")})

        if Chapter.objects.exclude(id=self.id).filter(title=self.title, release_date=self.release_date).exists():
            raise ValidationError(_("Контент с таким названием и годом выпуска уже существует."))

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or _("Без названия")

    class Meta:
        ordering = ['chapter_number']
        unique_together = ['franchise', 'chapter_number']
        verbose_name = _('Глава')
        verbose_name_plural = _('Главы')


# Эпизод
class Episode(models.Model):
    chapter = models.ForeignKey(Chapter, null=True, blank=True, related_name='episodes', on_delete=models.CASCADE, verbose_name=_('Глава'))
    episode_number = models.PositiveIntegerField(_('Номер эпизода'), blank=True, null=True)
    title = models.CharField(_('Название'), max_length=255, blank=True, null=True)
    video_file = models.FileField(_('Видеофайл'), upload_to='episode_videos/', blank=True, null=True)
    duration = models.DurationField(_('Длительность'), blank=True, null=True)
    release_date = models.DateField(_('Дата выхода'), blank=True, null=True)
    thumbnail_img = models.ImageField(_('Превью'), upload_to='episode_thumbnail_imgs/', blank=True, null=True)

    def __str__(self):
        return f"{self.chapter.title if self.chapter else 'No Chapter'} E{self.episode_number or '?'} - {self.title}"

    class Meta:
        ordering = ['episode_number']
        unique_together = ['chapter', 'episode_number']
        verbose_name = _('Эпизод')
        verbose_name_plural = _('Эпизоды')


# Персона
class Person(models.Model):
    first_name = models.CharField(_('Имя'), max_length=255, null=True)
    last_name = models.CharField(_('Фамилия'), max_length=255, null=True)
    birth_date = models.DateField(_('Дата рождения'), blank=True, null=True)
    country = models.CharField(_('Страна'), max_length=255, blank=True, null=True)
    photo_url = models.URLField(_('Ссылка на фото'), blank=True, null=True)
    biography = models.TextField(_('Биография'), blank=True, null=True)

    def get_absolute_url(self):
        return reverse('person_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = _('Персона')
        verbose_name_plural = _('Персоны')

    
# Связь Глава–Персона
class ChapterPersonRole(models.Model):
    ROLE_CHOICES = [
        ('actor', _('Актер')),
        ('director', _('Режиссер')),
        ('screenwriter', _('Сценарист')),
        ('producer', _('Продюсер')),
        ('editor', _('Монтажер')),
    ]

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='chapter_roles', null=True, blank=True, verbose_name=_('Глава'))
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='person_roles', null=True, blank=True, verbose_name=_('Персона'))
    role = models.CharField(_('Роль'), max_length=20, choices=ROLE_CHOICES, blank=True, null=True)

    def __str__(self):
        person_name = f"{self.person.first_name+' '+self.person.last_name}" if self.person else 'Unknown'
        chapter_title = self.chapter.title if self.chapter else 'No Chapter'
        return f"{person_name} как {self.get_role_display()} в {chapter_title}"

    class Meta:
        verbose_name = _('Роль в главе')
        verbose_name_plural = _('Роли в главах')
        unique_together = ['chapter', 'person', 'role']


# Комментарий
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments', verbose_name=_('Пользователь'))
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='comments', verbose_name=_('Глава'))
    text = models.TextField(_('Текст'))
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    likes_count = models.PositiveIntegerField(_('Лайки'), default=0)
    dislikes_count = models.PositiveIntegerField(_('Дизлайки'), default=0)

    class Meta:
        unique_together = ('user', 'chapter')
        ordering = ['-created_at']
        verbose_name = _('Комментарий')
        verbose_name_plural = _('Комментарии')

    def __str__(self):
        return f"Comment by {self.user.username if self.user else 'Unknown'} on {self.chapter.title}"

    def clean(self):
        banned_words = ['badword1', 'badword2', 'badword3']
        for word in banned_words:
            if re.search(r'\b' + re.escape(word) + r'\b', self.text, re.IGNORECASE):
                raise ValidationError(f"Комментарий содержит запрещённое слово: {word}")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# Отзывы
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True, verbose_name=_('Пользователь'))
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True, verbose_name=_('Глава'))
    text = models.TextField(_('Текст'), blank=True, null=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    likes_count = models.PositiveIntegerField(_('Лайки'), default=0)
    dislikes_count = models.PositiveIntegerField(_('Дизлайки'), default=0)

    def clean(self):
        super().clean()
        banned_words = ['badword1', 'offensivephrase', 'forbidden']
        if self.text:
            lowered = self.text.lower()
            for word in banned_words:
                if word in lowered:
                    raise ValidationError(f"Комментарий содержит запрещённое слово: {word}")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ['user', 'chapter']
        ordering = ['-created_at']
        verbose_name = _('Отзыв')
        verbose_name_plural = _('Отзывы')

    def __str__(self):
        return f"Review by {self.user.username if self.user else 'Unknown'} on {self.chapter.title if self.chapter else 'Unknown'}"


class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True, verbose_name=_('Пользователь'))
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True, verbose_name=_('Глава'))
    score = models.PositiveIntegerField(_('Оценка'), blank=True, null=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)

    class Meta:
        unique_together = ['user', 'chapter']
        verbose_name = _('Оценка')
        verbose_name_plural = _('Оценки')

    def __str__(self):
        return f"Rating by {self.user.username if self.user else 'Unknown'} on {self.chapter.title if self.chapter else 'Unknown'}"


# 1. Playlist
class Playlist(models.Model):
    user = models.ForeignKey(User, related_name='playlists', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Пользователь'))
    title = models.CharField(_('Название'), max_length=255, blank=True, null=True)
    description = models.TextField(_('Описание'), blank=True, null=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)
    is_public = models.BooleanField(_('Публичный'), default=False)
    cover_image_url = models.URLField(_('Ссылка на обложку'), blank=True, null=True)
    slug = models.SlugField(_('Слаг'), unique=True, blank=True, null=True)
    is_favorite = models.BooleanField(_('Избранное'), default=False)

    def get_absolute_url(self):
        return reverse('playlist_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title or 'untitled-playlist')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"'{self.title or 'Untitled'}' playlist of {self.user.username if self.user else 'Unknown'}"

    class Meta:
        ordering = ['title']
        verbose_name = _('Плейлист')
        verbose_name_plural = _('Плейлисты')

# 2. PlaylistChapter (Связь между плейлистом и главой)
class PlaylistChapter(models.Model):
    playlist = models.ForeignKey(Playlist, related_name='playlist_chapters', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Плейлист'))
    chapter = models.ForeignKey('Chapter', related_name='playlist_entries', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Глава'))
    added_at = models.DateTimeField(_('Добавлено'), auto_now_add=True)
    note = models.TextField(_('Заметка'), blank=True, null=True)

    def __str__(self):
        return f"{self.chapter.title if self.chapter else 'Unknown Chapter'} in {self.playlist.title if self.playlist else 'Unknown Playlist'}"

    class Meta:
        unique_together = ['playlist', 'chapter']
        ordering = ['-added_at']
        verbose_name = _('Глава в плейлисте')
        verbose_name_plural = _('Главы в плейлистах')

# 3. ViewHistory (История просмотров)
class ViewHistory(models.Model):
    user = models.ForeignKey(User, related_name='view_history', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Пользователь'))
    chapter = models.ForeignKey('Chapter', related_name='view_history', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Глава'))
    viewed_at = models.DateTimeField(_('Дата просмотра'), auto_now_add=True)

    class Meta:
        unique_together = ['user', 'chapter']
        ordering = ['-viewed_at']
        verbose_name = _('История просмотра')
        verbose_name_plural = _('Истории просмотров')

    def __str__(self):
        return f"{self.user.username if self.user else 'Unknown'} viewed {self.chapter.title if self.chapter else 'Unknown'} at {self.viewed_at}"