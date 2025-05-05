from rest_framework import viewsets
from .models import PlaylistChapter, ViewHistory, User, UserPaymentMethod, Subscription, UserSubscription, Genre, Franchise, Chapter, Episode, Person, ChapterPersonRole, Comment, Review, Rating, Playlist
from .serializers import ViewHistorySerializer, PlaylistChapterSerializer, UserSerializer, UserPaymentMethodSerializer, SubscriptionSerializer, UserSubscriptionSerializer, GenreSerializer, FranchiseSerializer, ChapterSerializer, EpisodeSerializer, PersonSerializer, ChapterPersonRoleSerializer, CommentSerializer, ReviewSerializer, RatingSerializer, PlaylistSerializer
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db.models.functions import ExtractYear
from rest_framework.filters import SearchFilter, OrderingFilter



# 1. User ViewSet
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# 2. UserPaymentMethod ViewSet
class UserPaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = UserPaymentMethod.objects.all()
    serializer_class = UserPaymentMethodSerializer

# 3. Subscription ViewSet
class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

# 4. UserSubscription ViewSet
class UserSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = UserSubscription.objects.all()
    serializer_class = UserSubscriptionSerializer

    def get_queryset(self):
        qs = UserSubscription.objects
        if self.action == 'list':
            qs = qs.active()
        return qs.select_related('user', 'subscription').prefetch_related('payment_methods')


# 5. Genre ViewSet
class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer

# 6. Franchise ViewSet
class FranchiseViewSet(viewsets.ModelViewSet):
    queryset = Franchise.objects.annotate(chapter_count=Count('chapters'))
    serializer_class = FranchiseSerializer

# 7. Chapter ViewSet

class ChapterFilter(FilterSet):
    q = CharFilter(field_name='title', lookup_expr='icontains', label='Search by title')
    genre = CharFilter(method='filter_by_genres', label='Genres (comma-separated)')
    exclude_genre = CharFilter(method='filter_exclude_genres', label='Exclude genres (comma-separated)')
    country = CharFilter(field_name='country', lookup_expr='icontains', label='Country')
    year = NumberFilter(method='filter_by_year', label='Release year')
    content_type = CharFilter(method='filter_by_content_types', label='Content types (comma-separated)')

    class Meta:
        model = Chapter
        fields = ['q', 'genre', 'exclude_genre', 'country', 'year', 'content_type']

    def filter_by_genres(self, queryset, name, value):
        genres = [v.strip() for v in value.split(',') if v.strip()]
        return queryset.filter(genres__name__in=genres).distinct()

    def filter_exclude_genres(self, queryset, name, value):
        genres_to_exclude = [v.strip() for v in value.split(',') if v.strip()]
        return queryset.exclude(genres__name__in=genres_to_exclude).distinct()

    def filter_by_year(self, queryset, name, value):
        return queryset.annotate(year=ExtractYear('release_date')).filter(year=value)

    def filter_by_content_types(self, queryset, name, value):
        types = [v.strip() for v in value.split(',') if v.strip()]
        return queryset.filter(content_type__in=types)



class ChapterViewSet(viewsets.ModelViewSet):
    queryset = Chapter.objects.all().select_related('franchise', 'required_subscription').prefetch_related('genres', 'people').order_by('-view_count')
    serializer_class = ChapterSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ChapterFilter
    search_fields = ['title']
    ordering_fields = ['rating_cache', 'release_date', 'view_count']


# 8. Episode ViewSet
class EpisodeViewSet(viewsets.ModelViewSet):
    queryset = Episode.objects.all()
    serializer_class = EpisodeSerializer

# 9. Person ViewSet
class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer

# 10. ChapterPersonRole ViewSet
class ChapterPersonRoleViewSet(viewsets.ModelViewSet):
    queryset = ChapterPersonRole.objects.all()
    serializer_class = ChapterPersonRoleSerializer

# 11. Comment ViewSet
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

# 12. Review ViewSet
class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

# 13. Rating ViewSet
class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

# 14. Playlist ViewSet
class PlaylistViewSet(viewsets.ModelViewSet):
    queryset = Playlist.objects.all()
    serializer_class = PlaylistSerializer

class PlaylistChapterViewSet(viewsets.ModelViewSet):
    queryset = PlaylistChapter.objects.select_related('playlist', 'chapter').all()
    serializer_class = PlaylistChapterSerializer

class ViewHistoryViewSet(viewsets.ModelViewSet):
    queryset = ViewHistory.objects.select_related('user', 'chapter').all()
    serializer_class = ViewHistorySerializer