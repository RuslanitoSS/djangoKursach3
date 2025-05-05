from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.exceptions import ValidationError
from django.db.models import Avg
from django.utils.text import slugify
import datetime
import re
from django.utils import timezone
from django.urls import reverse

# Пользователь
class User(AbstractUser):
    profile_pic = models.ImageField(upload_to='user_profile_pics/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    login_code = models.CharField(max_length=255, blank=True, null=True)  # поле для входа по коду

    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )

    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def get_absolute_url(self):
        return reverse('user_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.username

# 1. UserPaymentMethod
class UserPaymentMethod(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('card', 'Credit/Debit Card'),
        ('paypal', 'PayPal'),
        ('apple_pay', 'Apple Pay'),
        ('google_pay', 'Google Pay'),
        ('yoo_money', 'ЮMoney'),
        ('sbp', 'СБП'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    provider_id = models.CharField(max_length=255)
    masked_card_number = models.CharField(max_length=19, blank=True, null=True)
    card_brand = models.CharField(max_length=50, blank=True, null=True)
    card_expiry_month = models.IntegerField(blank=True, null=True)
    card_expiry_year = models.IntegerField(blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(blank=True, null=True)

    #автоматический расчёт срока действия карты. карта действует 5 лет с момента добавления
    """ def save(self, *args, **kwargs):
        if not self.valid_until:
            self.valid_until = self.added_at + datetime.timedelta(days=5*365)
        super().save(*args, **kwargs) """
    
    def save(self, *args, **kwargs):
        if not self.added_at:
            self.added_at = timezone.now()
        self.valid_until = self.added_at + datetime.timedelta(days=5*365)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.payment_type}"

# 2. Subscription
class Subscription(models.Model):
    title = models.CharField(max_length=255)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    description = models.TextField()

    def __str__(self):
        return self.title

class UserSubscriptionManager(models.Manager):
    
    #Получить все активные подписки
    #UserSubscription.objects.active()
    
    #Получить все истекшие подписки
    #UserSubscription.objects.expired()

    def active(self):
        now = timezone.now()
        return self.filter(is_active=True, start_date__lte=now, end_date__gte=now)


    def expired(self):
        now = timezone.now()
    
        # Исключаем подписки, которые неактивны
        return self.exclude(expiration_date__lt=now)
    
# 3. UserSubscription
class UserSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='user_subscriptions')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    payment_methods = models.ManyToManyField(UserPaymentMethod, related_name='subscriptions')
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    canceled_at = models.DateTimeField(blank=True, null=True)

    objects = UserSubscriptionManager()

    #для автоматического расчёта конца подписки
    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + datetime.timedelta(days=self.subscription.duration_days)
        super().save(*args, **kwargs)

    # метод, который определяет, активна ли подписка на момент запроса
    def is_currently_active(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date
    
    def __str__(self):
        return f"{self.user.username} - {self.subscription.title}"


# Жанры
class Genre(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

# Франшиза
class Franchise(models.Model):
    title = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def chapters_count(self):
        return self.chapters.count()

    def get_chapter_overview(self):
        return list(
            self.chapters.values(
                'id', 'chapter_number', 'franchise_relation'
            ).order_by('chapter_number')
        )

    def __str__(self):
        return self.title or "Unnamed Franchise"

# Глава
class Chapter(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('movie', 'Фильм'),
        ('series', 'Сериал'),
    ]
    FRANCHISE_RELATION_CHOICES = [
    ('main', 'Основная история'),
    ('spinoff', 'Спин-офф'),
    ('side', 'Побочная история'),
    ('other', 'Другое'),
]

    franchise_relation = models.CharField(
        max_length=20,
        choices=FRANCHISE_RELATION_CHOICES,
        blank=True,
        null=True,
        help_text="Тип связи главы с франшизой (например, основная история, спин-офф и т.д.)"
    )
    franchise = models.ForeignKey(Franchise, related_name='chapters', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    release_date = models.DateField(blank=True, null=True)
    required_subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True)
    chapter_number = models.PositiveIntegerField(blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    age_rating = models.PositiveIntegerField(blank=True, null=True)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, blank=True, null=True)
    rating_cache = models.FloatField(default=0.0)
    view_count = models.PositiveIntegerField(default=0)
    poster_image = models.ImageField(upload_to='chapter_posters/', blank=True, null=True)
    trailer_url = models.URLField(blank=True, null=True) 
    
    genres = models.ManyToManyField(Genre, related_name='chapters', blank=True)
    people = models.ManyToManyField('Person', through='ChapterPersonRole', related_name='chapters', blank=True)

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

        # Валидация обязательных полей
        required_fields = {
            'title': self.title,
            'release_date': self.release_date,
            'content_type': self.content_type,
            'age_rating': self.age_rating,
        }

        for field_name, value in required_fields.items():
            if not value:
                raise ValidationError({field_name: f"Поле '{field_name}' обязательно для заполнения."})

        # Проверка: дата релиза не может быть в будущем
        if self.release_date and self.release_date > datetime.date.today():
            raise ValidationError({'release_date': "Дата релиза не может быть в будущем."})

        # Проверка диапазона возрастного рейтинга
        if self.age_rating and not (0 <= self.age_rating <= 21):
            raise ValidationError({'age_rating': "Возрастной рейтинг должен быть от 0 до 21."})

        # Валидация уникальности фильма или сериала
        if Chapter.objects.exclude(id=self.id).filter(title=self.title, release_date=self.release_date).exists():
            raise ValidationError("Контент с таким названием и годом выпуска уже существует.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure validation is called before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or "Untitled Chapter"

    class Meta:
        ordering = ['chapter_number']
        unique_together = ['franchise', 'chapter_number']


# Эпизод
class Episode(models.Model):
    chapter = models.ForeignKey(Chapter, null=True, blank=True, related_name='episodes', on_delete=models.CASCADE)
    episode_number = models.PositiveIntegerField(blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    video_file = models.FileField(upload_to='episode_videos/', blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)
    release_date = models.DateField(blank=True, null=True)
    thumbnail_img = models.ImageField(upload_to='episode_thumbnail_imgs/', blank=True, null=True)

    def __str__(self):
        return f"{self.chapter.title if self.chapter else 'No Chapter'} E{self.episode_number or '?'} - {self.title}"

    class Meta:
        ordering = ['episode_number']
        unique_together = ['chapter', 'episode_number']


# Персона
class Person(models.Model):
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    birth_date = models.DateField(blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    photo_url = models.URLField(blank=True, null=True)
    biography = models.TextField(blank=True, null=True)

    def get_absolute_url(self):
        return reverse('person_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    
# Связь Глава–Персона
class ChapterPersonRole(models.Model):
    ROLE_CHOICES = [
        ('actor', 'Actor'),
        ('director', 'Director'),
        ('screenwriter', 'Screenwriter'),
        ('producer', 'Producer'),
        ('editor', 'Editor'),
    ]

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='chapter_roles', null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='person_roles', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.person.first_name+' '+self.person.last_name if self.person else 'Unknown'} as {self.role} in {self.chapter.title if self.chapter else 'No Chapter'}"


# Комментарий
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    likes_count = models.PositiveIntegerField(default=0)
    dislikes_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'chapter')
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user.username if self.user else 'Unknown'} on {self.chapter.title}"

    def clean(self):
        # Проверка на запрещённые слова
        banned_words = ['badword1', 'badword2', 'badword3']  # Пример списка запрещённых слов
        for word in banned_words:
            if re.search(r'\b' + re.escape(word) + r'\b', self.text, re.IGNORECASE):
                raise ValidationError(f"Комментарий содержит запрещённое слово: {word}")

    def save(self, *args, **kwargs):
        self.full_clean()  # Выполнение валидации при сохранении
        super().save(*args, **kwargs)


# Отзывы

class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    likes_count = models.PositiveIntegerField(default=0)
    dislikes_count = models.PositiveIntegerField(default=0)

    def clean(self):
        super().clean()
        banned_words = ['badword1', 'offensivephrase', 'forbidden']  # замените на реальные
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

    def __str__(self):
        return f"Review by {self.user.username if self.user else 'Unknown'} on {self.chapter.title if self.chapter else 'Unknown'}"


class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True)
    score = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'chapter']

    def __str__(self):
        return f"Rating by {self.user.username if self.user else 'Unknown'} on {self.chapter.title if self.chapter else 'Unknown'}"


# 1. Playlist
class Playlist(models.Model):
    user = models.ForeignKey(User, related_name='playlists', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=False)
    cover_image_url = models.URLField(blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    is_favorite = models.BooleanField(default=False)

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

# 2. PlaylistChapter (Связь между плейлистом и главой)
class PlaylistChapter(models.Model):
    playlist = models.ForeignKey(Playlist, related_name='playlist_chapters', on_delete=models.CASCADE, null=True, blank=True)
    chapter = models.ForeignKey('Chapter', related_name='playlist_entries', on_delete=models.CASCADE, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.chapter.title if self.chapter else 'Unknown Chapter'} in {self.playlist.title if self.playlist else 'Unknown Playlist'}"

    class Meta:
        unique_together = ['playlist', 'chapter']
        ordering = ['-added_at']

# 3. ViewHistory (История просмотров)
class ViewHistory(models.Model):
    user = models.ForeignKey(User, related_name='view_history', on_delete=models.CASCADE, null=True, blank=True)
    chapter = models.ForeignKey('Chapter', related_name='view_history', on_delete=models.CASCADE, null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'chapter']
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user.username if self.user else 'Unknown'} viewed {self.chapter.title if self.chapter else 'Unknown'} at {self.viewed_at}"
