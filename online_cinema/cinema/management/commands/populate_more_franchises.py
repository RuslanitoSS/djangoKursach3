import datetime
from django.db import transaction
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

from cinema.models import Genre, Franchise, Chapter, Person, Episode, ChapterPersonRole


class Command(BaseCommand):
    help = 'Добавляет 5 новых франшиз (MCU, Джон Уик, Форсаж, Миссия невыполнима, Звёздные войны) со всеми связанными данными'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🎬 Начинаем добавление 5 новых франшиз в базу данных...'))

        with transaction.atomic():
            # ================= 1. ДОПОЛНИТЕЛЬНЫЕ ЖАНРЫ =================
            self.stdout.write('🎭 Создаём жанры...')
            genres = self._setup_genres()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Всего жанров: {len(genres)}'))

            # ================= 2. НОВЫЕ ФРАНШИЗЫ =================
            self.stdout.write('📚 Создаём франшизы...')
            new_franchises = self._setup_franchises()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано франшиз: {len(new_franchises)}'))

            # ================= 3. НОВЫЕ ПЕРСОНЫ =================
            self.stdout.write('👤 Создаём персон...')
            new_persons = self._setup_persons()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано персон: {len(new_persons)}'))

            # ================= 4. ГЛАВЫ + ЖАНРЫ =================
            self.stdout.write('🎞️ Создаём главы (фильмы/сериалы)...')
            chapters = self._setup_chapters(new_franchises, genres)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано глав: {len(chapters)}'))

            # ================= 5. ЭПИЗОДЫ =================
            self.stdout.write('📼 Создаём эпизоды...')
            episodes_count = self._setup_episodes(chapters)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано эпизодов: {episodes_count}'))

            # ================= 6. РОЛИ (ChapterPersonRole) =================
            self.stdout.write('🔗 Создаём связи персон с главами...')
            created_roles = self._setup_roles(chapters, new_persons)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано ролевых связей: {created_roles}'))

            # ================= ИТОГ =================
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('✅ ГОТОВО! Статистика добавлений:'))
            self.stdout.write('='*60)
            self.stdout.write(f"🎭 Жанров (всего):        {Genre.objects.count()}")
            self.stdout.write(f"📚 Франшиз (всего):       {Franchise.objects.count()}")
            self.stdout.write(f"👤 Персон (всего):        {Person.objects.count()}")
            self.stdout.write(f"🎞️ Глав (всего):          {Chapter.objects.count()}")
            self.stdout.write(f"📼 Эпизодов (всего):      {Episode.objects.count()}")
            self.stdout.write(f"🔗 Ролевых связей (всего): {ChapterPersonRole.objects.count()}")
            self.stdout.write('='*60)

    # ================= ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =================

    def _setup_genres(self):
        """Создаёт или получает жанры"""
        new_genre_names = [
            "Научная фантастика", "Комедия", "Ужасы", "Военный",
            "Исторический", "Фантастика", "Спорт"
        ]
        existing_names = [
            "Фэнтези", "Приключения", "Боевик", "Криминал", "Драма",
            "Триллер", "Семейный", "Мистика", "Документальный"
        ]
        all_names = new_genre_names + existing_names

        genres = {}
        for name in all_names:
            g, _ = Genre.objects.get_or_create(name=name)
            genres[name] = g
        return genres

    def _setup_franchises(self):
        """Создаёт или получает франшизы"""
        franchise_data = {
            "mcu": "Marvel Cinematic Universe",
            "johnwick": "Джон Уик",
            "fast": "Форсаж",
            "mi": "Миссия невыполнима",
            "starwars": "Звёздные войны",
        }
        franchises = {}
        for key, title in franchise_data.items():
            f, _ = Franchise.objects.get_or_create(title=title)
            franchises[key] = f
        return franchises

    def _setup_persons(self):
        """Создаёт или получает персон"""
        persons_data = [
            # MCU
            ("Джон", "Фавро", "1966-10-19", "США", "Режиссёр и продюсер, запустивший киновселенную Marvel фильмом «Железный человек»."),
            ("Джо", "Руссо", "1971-07-18", "США", "Режиссёр, снявший «Мстители: Война бесконечности» и «Финал» вместе с братом."),
            ("Энтони", "Руссо", "1970-02-03", "США", "Режиссёр, соавтор крупнейших проектов MCU."),
            ("Роберт", "Дауни-мл.", "1965-04-04", "США", "Актёр, прославившийся ролью Тони Старка / Железного человека."),
            ("Крис", "Эванс", "1981-06-13", "США", "Актёр, исполнивший роль Стива Роджерса / Капитана Америки."),
            ("Скарлетт", "Йоханссон", "1984-11-22", "США", "Актриса, сыгравшая Наташу Романофф / Чёрную вдову."),
            ("Кевин", "Файги", "1973-06-02", "США", "Президент Marvel Studios, главный продюсер киновселенной."),
            # Джон Уик
            ("Чад", "Стахелски", "1968-09-20", "США", "Режиссёр и каскадёр, создавший стиль боевиков «Джон Уик»."),
            ("Киану", "Ривз", "1964-09-02", "Канада", "Актёр, исполнивший главную роль в серии «Джон Уик»."),
            ("Лоренс", "Фишберн", "1961-07-30", "США", "Актёр, сыгравший «Короля подполья» Боуери Кинга."),
            ("Иэн", "Макшейн", "1942-09-29", "Великобритания", "Актёр, исполнитель роли владельца отеля «Континенталь»."),
            # Форсаж
            ("Джастин", "Лин", "1977-02-11", "США", "Режиссёр, вернувший франшизу к уличным гонкам в «Форсаж 6»."),
            ("Вин", "Дизель", "1967-07-18", "США", "Актёр и продюсер, исполнитель роли Доминика Торетто."),
            ("Дуэйн", "Джонсон", "1972-05-02", "США", "Актёр, сыгравший Люка Хоббса в серии «Форсаж»."),
            ("Мишель", "Родригес", "1978-07-12", "США", "Актриса, исполнившая роль Летиции Ортис."),
            # Миссия невыполнима
            ("Кристофер", "Маккуорри", "1968-01-01", "США", "Сценарист и режиссёр, работающий с Томом Крузом над серией МН."),
            ("Том", "Круз", "1962-07-03", "США", "Актёр и продюсер, исполнитель роли Итана Ханта с 1996 года."),
            ("Ребекка", "Фергюсон", "1983-10-19", "Швеция", "Актриса, сыгравшая Ильзу Фауст в нескольких фильмах серии."),
            ("Саймон", "Пегг", "1970-02-14", "Великобритания", "Актёр, исполнитель роли Бенджи Данна."),
            # Звёздные войны
            ("Джордж", "Лукас", "1944-05-14", "США", "Создатель вселенной «Звёздные войны», режиссёр оригинальной трилогии."),
            ("Джей Джей", "Абрамс", "1966-06-27", "США", "Режиссёр, возродивший сагу фильмом «Пробуждение силы»."),
            ("Харрисон", "Форд", "1942-07-13", "США", "Актёр, прославившийся ролью Хана Соло."),
            ("Марк", "Хэмилл", "1951-09-25", "США", "Актёр, исполнивший роль Люка Скайуокера."),
            ("Кэрри", "Фишер", "1956-10-21", "США", "Актриса, сыгравшая принцессу Лею Органу."),
            ("Дэйзи", "Ридли", "1992-04-10", "Великобритания", "Актриса, исполнительница роли Рей в новой трилогии."),
        ]

        persons = {}
        for first, last, birth, country, bio in persons_data:
            p, _ = Person.objects.get_or_create(
                first_name=first, last_name=last,
                defaults={
                    "birth_date": datetime.date.fromisoformat(birth),
                    "country": country,
                    "biography": bio,
                    "photo_url": f"https://example.com/persons/{first.lower()}_{last.lower()}.jpg"
                }
            )
            persons[f"{first}_{last}"] = p
        return persons

    def _create_chapter(self, fk_franchise, num, title, date, country, rating, ctype, rel, desc, poster, trailer, genre_keys, genres):
        """Вспомогательный метод для создания главы"""
        ch, _ = Chapter.objects.get_or_create(
            franchise=fk_franchise, chapter_number=num,
            defaults={
                "title": title, "release_date": datetime.date.fromisoformat(date),
                "country": country, "age_rating": rating, "content_type": ctype,
                "franchise_relation": rel, "description": desc,
                "poster_image": f"posters/{poster}", "trailer_url": trailer,
                "rating_cache": 0.0, "view_count": 0, "required_subscription": None
            }
        )
        ch.genres.set([genres[k] for k in genre_keys])
        return ch

    def _setup_chapters(self, franchises, genres):
        """Создаёт главы для всех франшиз"""
        chapters = {}

        # 🦸 MCU
        chapters["mcu_1"] = self._create_chapter(
            franchises["mcu"], 1, "Железный человек", "2008-05-02", "США", 12, "movie", "main",
            "Миллиардер Тони Старк создаёт высокотехнологичный костюм и становится супергероем.", "mcu_ironman.jpg",
            "https://www.youtube.com/watch?v=8ugaeA-nMTc", ["Боевик", "Научная фантастика", "Приключения"], genres)
        chapters["mcu_2"] = self._create_chapter(
            franchises["mcu"], 2, "Мстители", "2012-05-04", "США", 12, "movie", "main",
            "Ник Фьюри собирает команду супергероев для защиты Земли от инопланетного вторжения.", "mcu_avengers.jpg",
            "https://www.youtube.com/watch?v=eOrNdBpGMv8", ["Боевик", "Научная фантастика", "Приключения"], genres)
        chapters["mcu_3"] = self._create_chapter(
            franchises["mcu"], 3, "Мстители: Финал", "2019-04-26", "США", 12, "movie", "main",
            "Оставшиеся в живых Мстители объединяются, чтобы отменить действия Таноса.", "mcu_endgame.jpg",
            "https://www.youtube.com/watch?v=TcMBFSGVi1c", ["Боевик", "Научная фантастика", "Драма"], genres)

        # 🔫 Джон Уик
        chapters["jw_1"] = self._create_chapter(
            franchises["johnwick"], 1, "Джон Уик", "2014-10-24", "США", 18, "movie", "main",
            "Бывший киллер выходит на пенсию, но месть заставляет его вернуться к делу.", "jw1.jpg",
            "https://www.youtube.com/watch?v=C0BMx-qxsP4", ["Боевик", "Криминал", "Триллер"], genres)
        chapters["jw_2"] = self._create_chapter(
            franchises["johnwick"], 2, "Джон Уик 2", "2017-02-10", "США", 18, "movie", "main",
            "Джон вынужден выполнить обещание и сталкивается с международной гильдией убийц.", "jw2.jpg",
            "https://www.youtube.com/watch?v=ChpLV9AMqm4", ["Боевик", "Криминал", "Триллер"], genres)
        chapters["jw_3"] = self._create_chapter(
            franchises["johnwick"], 3, "Джон Уик 3", "2019-05-17", "США", 18, "movie", "main",
            "Объявленный вне закона, Джон сражается за выживание в мире наёмников.", "jw3.jpg",
            "https://www.youtube.com/watch?v=M7XM597XO94", ["Боевик", "Криминал", "Триллер"], genres)

        # 🚗 Форсаж
        chapters["fast_1"] = self._create_chapter(
            franchises["fast"], 1, "Форсаж", "2001-06-22", "США", 16, "movie", "main",
            "Полицейский внедряется в мир уличных гонок Лос-Анджелеса.", "fast1.jpg",
            "https://www.youtube.com/watch?v=2TAOizOnlNw", ["Боевик", "Криминал", "Приключения"], genres)
        chapters["fast_5"] = self._create_chapter(
            franchises["fast"], 5, "Форсаж 5", "2011-04-29", "США", 16, "movie", "main",
            "Дом и Брайан собирают команду для ограбления в Рио-де-Жанейро.", "fast5.jpg",
            "https://www.youtube.com/watch?v=mw2AqdB5EVA", ["Боевик", "Криминал", "Приключения"], genres)
        chapters["fast_9"] = self._create_chapter(
            franchises["fast"], 9, "Форсаж 9", "2021-06-25", "США", 16, "movie", "main",
            "Дом сталкивается с прошлым, когда появляется его брат-предатель.", "fast9.jpg",
            "https://www.youtube.com/watch?v=FUK2kdPsBws", ["Боевик", "Криминал", "Приключения"], genres)

        # 🕵️ Миссия невыполнима
        chapters["mi_4"] = self._create_chapter(
            franchises["mi"], 4, "Миссия невыполнима: Протокол Фантом", "2011-12-16", "США", 12, "movie", "main",
            "Итан Хант и команда очищают имя агентства после взрыва в Кремле.", "mi4.jpg",
            "https://www.youtube.com/watch?v=EDGYVFZxsxw", ["Боевик", "Триллер", "Приключения"], genres)
        chapters["mi_6"] = self._create_chapter(
            franchises["mi"], 6, "Миссия невыполнима: Последствия", "2018-07-27", "США", 12, "movie", "main",
            "Итан должен предотвратить глобальную катастрофу, выбирая между миссией и жизнью друзей.", "mi6.jpg",
            "https://www.youtube.com/watch?v=wb49-oV0F78", ["Боевик", "Триллер", "Приключения"], genres)
        chapters["mi_7"] = self._create_chapter(
            franchises["mi"], 7, "Миссия невыполнима: Смертельная расплата. Часть 1", "2023-07-12", "США", 12, "movie", "main",
            "Итан сталкивается с искусственным интеллектом, угрожающим всему миру.", "mi7.jpg",
            "https://www.youtube.com/watch?v=avz06PDqDbM", ["Боевик", "Триллер", "Научная фантастика"], genres)

        # ⚔️ Звёздные войны
        chapters["sw_4"] = self._create_chapter(
            franchises["starwars"], 4, "Звёздные войны. Эпизод IV: Новая надежда", "1977-05-25", "США", 6, "movie", "main",
            "Люк Скайуокер присоединяется к повстанцам, чтобы спасти принцессу Лею и уничтожить Звезду Смерти.", "sw4.jpg",
            "https://www.youtube.com/watch?v=vZ734NWnAHA", ["Фантастика", "Фэнтези", "Приключения"], genres)
        chapters["sw_7"] = self._create_chapter(
            franchises["starwars"], 7, "Звёздные войны: Пробуждение силы", "2015-12-18", "США", 6, "movie", "main",
            "Новое поколение героев сталкивается с угрозой Первого ордена.", "sw7.jpg",
            "https://www.youtube.com/watch?v=sGbxmsDFVnE", ["Фантастика", "Фэнтези", "Приключения"], genres)
        chapters["sw_9"] = self._create_chapter(
            franchises["starwars"], 9, "Звёздные войны: Скайуокер. Восход", "2019-12-20", "США", 6, "movie", "main",
            "Финальная битва между джедаями и ситхами за судьбу галактики.", "sw9.jpg",
            "https://www.youtube.com/watch?v=8Qn_spdM5Zg", ["Фантастика", "Фэнтези", "Приключения"], genres)

        # Сериал: «Мандалорец»
        chapters["sw_series"] = self._create_chapter(
            franchises["starwars"], 10, "Мандалорец: Сезон 1", "2019-11-12", "США", 12, "series", "spinoff",
            "Одинокий охотник за головами в далёкой галактике защищает таинственного ребёнка.", "mando_s1.jpg",
            "https://www.youtube.com/watch?v=aOC8E8z_ifw", ["Фантастика", "Приключения", "Боевик"], genres)

        return chapters

    def _setup_episodes(self, chapters):
        """Создаёт эпизоды для глав"""
        def create_episode(ch, num, title, hours, mins, file, thumb, date_override=None):
            Episode.objects.get_or_create(
                chapter=ch, episode_number=num,
                defaults={
                    "title": title, "video_file": f"media/{file}",
                    "duration": datetime.timedelta(hours=hours, minutes=mins),
                    "release_date": date_override or ch.release_date,
                    "thumbnail_img": f"thumbs/{thumb}"
                }
            )

        # 1 эпизод на каждый фильм
        film_chapters = [
            ("mcu_1", 2, 6), ("mcu_2", 2, 23), ("mcu_3", 3, 1),
            ("jw_1", 1, 41), ("jw_2", 2, 10), ("jw_3", 2, 11),
            ("fast_1", 1, 46), ("fast_5", 2, 10), ("fast_9", 2, 23),
            ("mi_4", 2, 13), ("mi_6", 2, 27), ("mi_7", 2, 43),
            ("sw_4", 2, 1), ("sw_7", 2, 16), ("sw_9", 2, 22),
        ]
        for ch_key, h, m in film_chapters:
            ch = chapters[ch_key]
            create_episode(ch, 1, f"{ch.title} (Полная версия)", h, m, f"{ch_key}.mp4", f"{ch_key}_thumb.jpg")

        # 2 эпизода для сериала «Мандалорец»
        ch_mando = chapters["sw_series"]
        create_episode(ch_mando, 1, "Глава 1: Мандалорец", 0, 39, "mando_ep1.mp4", "mando_ep1.jpg", datetime.date(2019, 11, 12))
        create_episode(ch_mando, 2, "Глава 2: Дитя", 0, 32, "mando_ep2.mp4", "mando_ep2.jpg", datetime.date(2019, 11, 15))

        return Episode.objects.filter(chapter__in=chapters.values()).count()

    def _setup_roles(self, chapters, new_persons):
        """Создаёт связи персон с главами"""
        roles_data = {
            # MCU
            "mcu_1": [("director", "Джон_Фавро"), ("producer", "Кевин_Файги"), ("actor", "Роберт_Дауни-мл.")],
            "mcu_2": [("director", "Джосс_Уидон"), ("producer", "Кевин_Файги"), ("actor", "Роберт_Дауни-мл."), ("actor", "Крис_Эванс"), ("actor", "Скарлетт_Йоханссон")],
            "mcu_3": [("director", "Джо_Руссо"), ("director", "Энтони_Руссо"), ("producer", "Кевин_Файги"), ("actor", "Роберт_Дауни-мл."), ("actor", "Крис_Эванс")],
            # Джон Уик
            "jw_1": [("director", "Чад_Стахелски"), ("actor", "Киану_Ривз"), ("actor", "Иэн_Макшейн")],
            "jw_2": [("director", "Чад_Стахелски"), ("actor", "Киану_Ривз"), ("actor", "Лоренс_Фишберн")],
            "jw_3": [("director", "Чад_Стахелски"), ("actor", "Киану_Ривз"), ("actor", "Иэн_Макшейн")],
            # Форсаж
            "fast_1": [("director", "Роб_Коэн"), ("actor", "Вин_Дизель"), ("actor", "Мишель_Родригес")],
            "fast_5": [("director", "Джастин_Лин"), ("actor", "Вин_Дизель"), ("actor", "Дуэйн_Джонсон"), ("actor", "Мишель_Родригес")],
            "fast_9": [("director", "Джастин_Лин"), ("actor", "Вин_Дизель"), ("actor", "Мишель_Родригес")],
            # Миссия невыполнима
            "mi_4": [("director", "Брэд_Бёрд"), ("actor", "Том_Круз"), ("actor", "Саймон_Пегг")],
            "mi_6": [("director", "Кристофер_Маккуорри"), ("actor", "Том_Круз"), ("actor", "Ребекка_Фергюсон"), ("actor", "Саймон_Пегг")],
            "mi_7": [("director", "Кристофер_Маккуорри"), ("actor", "Том_Круз"), ("actor", "Ребекка_Фергюсон")],
            # Звёздные войны
            "sw_4": [("director", "Джордж_Лукас"), ("actor", "Харрисон_Форд"), ("actor", "Марк_Хэмилл"), ("actor", "Кэрри_Фишер")],
            "sw_7": [("director", "Джей_Джей_Абрамс"), ("actor", "Харрисон_Форд"), ("actor", "Дэйзи_Ридли")],
            "sw_9": [("director", "Джей_Джей_Абрамс"), ("actor", "Марк_Хэмилл"), ("actor", "Дэйзи_Ридли")],
            "sw_series": [("director", "Дэйв_Филони"), ("actor", "Педро_Паскаль")],
        }

        created_roles = 0
        for ch_key, role_list in roles_data.items():
            ch = chapters[ch_key]
            for role, person_key in role_list:
                p = new_persons.get(person_key)
                if not p:
                    # Создаём заглушку, если персоны нет в списке
                    parts = person_key.split("_", 1) if "_" in person_key else (person_key, "")
                    first, last = parts if len(parts) == 2 else (parts[0], "")
                    p, _ = Person.objects.get_or_create(
                        first_name=first, last_name=last,
                        defaults={"biography": f"Персона для франшизы {ch_key}"}
                    )
                ChapterPersonRole.objects.get_or_create(chapter=ch, person=p, role=role)
                created_roles += 1
        return created_roles