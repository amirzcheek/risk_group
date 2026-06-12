# Поля Платонуса для модели группы риска

Справочник: какие таблицы и поля реальной инсталляции Платонуса нужны системе
раннего предупреждения. Составлен по портфелю студента (StudentID 2910, КНУС /
Академия физкультуры). Отдайте этот список тому, у кого read-only доступ к базе.

Поля сгруппированы по 6 логическим запросам из [data_queries.yaml](data_queries.yaml).
Для каждого указано: реальная таблица.поле → роль в модели.

> ⚠️ Доступ строго **read-only (SELECT)**. Тянуть только перечисленное, без ПДн
> (см. раздел «Не выгружать»). Ключевое поле — **`week`**: номер недели семестра
> события; именно оно даёт временной срез без утечки данных.

---

## 0. Целевая метка — отчисление / восстановление (ОБЯЗАТЕЛЬНО)

Без неё модель не обучить. Логический запрос: **`status_events`**.

| Таблица | Поле | Роль |
|---|---|---|
| `students` | `hpeo_expulsion_date` | дата приказа об отчислении → метка `expelled` |
| `students` | `hpeo_expulsion_order_number` | номер приказа об отчислении |
| `students` | `isStudent` | 0 = уже не студент (выбыл) |
| `students` | `isinretire` | в процессе отчисления |
| `students` | `blocked` | заблокирован |
| `student_info` | `deductDate` | дата отчисления |
| `student_info` | `deductYear` | год отчисления |
| `student_info` | `deductOrderNumber` | номер приказа |
| `order_section_student_states` | `studentID`, `sectionID`, `groupID`, `oldGroupID`, `course`, `oldCourse` | приказы о движении контингента |
| `orderstudentinfo` | `deduct_to`, `enter_from`, `isinretire`, `isStudent`, `study_year`, `term` | тип приказа (отчисл./восст./академ) |
| `ssc_applications` | `academic_leave_start`, `academic_leave_end` | академический отпуск → метка `academic_leave` |
| `ssc_applications` | `application_submit_reason_ru`, `current_status`, `current_status_date` | основание/статус заявления |
| `university_applicant_info` | `recovered_time`, `recovered_person`, `status` | восстановление → метка `reinstated` |
| `queries` | `recoverable_date` | дата восстановления |

**Как формируется метка:** `event_type = expelled`, если есть `hpeo_expulsion_date`
(или `deductDate` / `isStudent=0` / приказ об отчислении). `week` события = номер
недели семестра, вычисленный из даты относительно начала семестра.

---

## 1. Студенты — демография и статика (ОБЯЗАТЕЛЬНО)

Логический запрос: **`students`**. Статические признаки + ключ для остальных.

| Таблица | Поле | Роль / признак модели |
|---|---|---|
| `students` | `StudentID` | ключ (стабильный внутренний ID) |
| `students` | `BirthDate` | → возраст (`age`) |
| `students` | `CourseNumber` | курс (`course_year`); первокурсники рискованнее |
| `students` | `SexID` | пол (`is_male`) — через справочник |
| `students` | `PaymentFormID` / `grant_type` / `fundingID` | форма оплаты (`is_paid`: грант/платное) |
| `students` | `StudyFormID` | форма обучения (очная/заочная) |
| `students` | `StudyLanguageID` | язык обучения |
| `students` | `ProfessionID`, `specializationID`, `groupID` | направление / специализация / группа |
| `students` | `GPA` | текущий GPA |
| `students` | `currentCreditsSum`, `creditsSum` | накопленные кредиты (нагрузка/прогресс) |
| `students` | `sum_points`, `rating` | баллы ЕНТ при поступлении |
| `students` | **`has_debts`** | финансовая задолженность — сильный сигнал риска |
| `students` | **`has_job`** | работает (риск ↑) |
| `students` | `dorm_state` | общежитие (иногородний прокси) |
| `students` | `StartDate`, `enroll_order_date` | дата зачисления → стаж обучения |
| `student_info` | **`certificateAverageScore`**, `previous_gpa` | средний балл аттестата ≈ `entry_gpa` |
| `student_info` | `gradeThreeCount`, `gradeFourCount`, `gradeFiveCount` | тройки/четвёрки/пятёрки в аттестате (бэкграунд) |
| `student_info` | `education_condition_id`, `fromAreaID`, `from_region` | условия / география (иногородний) |

**Нужен учебный период (`term`)** для каждого студента — из `orderstudentinfo.study_year`/`term`
или из активной учебной группы.

---

## 2. Оценки (ОБЯЗАТЕЛЬНО — главный сигнал)

Логический запрос: **`grades`**.

| Таблица | Поле | Роль / признак модели |
|---|---|---|
| `journal` | `StudentID`, `Mark`, **`week`**, `MarkDate`, `markTypeID`, `number`, `retakeID`, `isCurrent`, `StudyGroupID` | понедельная динамика баллов (`avg_score`, `score_trend`); срез без утечки |
| `totalmarks` | `studentID`, `avermark`, `rating`, `totalmark`, `exammark`, `is_passed`, `success`, `controlformid`, `course`, `credits`, `subjectCode`, `subjectID` | итоговые баллы по дисциплинам, провалы |
| `transcript` | `StudentID`, `subjectcode`, `NumeralMark`, `AlphaMark`, `TotalMark`, `is_passed`, `retake`, `wasRetaken`, `re_exam_count`, `Credits`, `coursenumber`, `term`, `subjectID` | F-оценки (`fail_rate`), пересдачи (`retake_count`), ключевые предметы |
| `er_marks` | `studentID`, `mark`, `traditionalMark`, `markTypeID`, `created` | рубежные отметки |
| `testingstudents` | `studentID`, `mark`, `term_number`, `traditionalMark`, `status` | результаты тестирований |

**Ключевые предметы (`is_key_course`):** отметьте профилирующие дисциплины по
`transcript.subject_type` / списку `subjectCode` вашей ОП (например, для B005 —
профильные методики, физиология). Можно вынести список кодов в конфиг.

---

## 3. Посещаемость (ОБЯЗАТЕЛЬНО)

Логический запрос: **`attendance`**.

| Таблица | Поле | Роль / признак модели |
|---|---|---|
| `totalmarks` | **`absence_percentage`**, `absence` | прямой % пропусков по дисциплине (`attendance_rate`) |
| `journal` | `Mark`, `markTypeID`, `gradeType`, **`week`** | отметки посещаемости по неделям (`attendance_trend`, `absent_weeks`) |
| `studentstudygroup` | `studyGroupID`, `StudentID`, `qr_attendance_type` | привязка к группам / тип учёта посещаемости |

> Если посещаемость в `journal` помечается отдельным `markTypeID` — отфильтруйте
> по нему. Иначе используйте агрегат `totalmarks.absence_percentage`.

---

## 4. Сдачи заданий и дедлайны (ЖЕЛАТЕЛЬНО)

Логический запрос: **`submissions`**.

| Таблица | Поле | Роль / признак модели |
|---|---|---|
| `assignment_recipients` | `studentID`, `assignmentID`, `recipient_status`, `assessment_provided`, `assessment_setted`, **`assessment_week`**, `startDate`, `endDate`, `assessment_date`, `justification`, `numberOfRating` | сдано / не сдано / не в срок (`late_or_missing_rate`, `missing_count`) |
| `journal_permission` | `student_id`, `week`, `accepted` | допуски к рубежному контролю по неделям |
| `mark_application_journal_permission` | `studentID`, `week`, `mark`, `markForm` | заявки на отметку / допуски |

«Не в срок» = `assessment_date > endDate`; «не сдано» = `recipient_status` без сдачи /
`assessment_provided = 0`.

---

## 5. Активность (ОПЦИОНАЛЬНО — прокси)

Логический запрос: **`activity`**. ⚠️ Явных логов входа в LMS в выгрузке нет.
Используйте прокси активности (или временно отключите блок — модель работает без него).

| Таблица | Поле | Роль / прокси |
|---|---|---|
| `journal` | `MarkDate`, `week` | частота отметок по неделям (вовлечённость) |
| `assignment_recipients` | `assessment_date`, `assessment_week` | активность по заданиям |
| `testing_attempts` | `studentID`, `start_date`, `finish_time` | активность в тестированиях |
| `student_notifications` | `studentID`, `modified`, `state` | реакция на уведомления (слабый прокси) |
| `test_logs` | `studentID`, `log_date` | системная активность |

---

## 6. Справочники (раскодировать ID)

Тянуть соответствующие dict-таблицы Платонуса или захардкодить маппинг в SQL:

- `SexID` → пол
- `PaymentFormID`, `grant_type`, `fundingID` → форма оплаты (грант/платное)
- `StudyFormID` → форма обучения
- `StudyLanguageID` → язык
- `ProfessionID`, `specializationID` → направление/специализация
- `groupID` / `StudyGroupID` → учебная группа (название)
- `markTypeID`, `gradeType` → тип отметки (нужно отличать оценку от посещаемости)
- `controlformid` → форма контроля (экзамен/зачёт/курсовая)

---

## 🚫 НЕ выгружать (ПДн и секреты)

Модели не нужны и наружу выходить НЕ должны:

- ИИН, ФИО (RU/KZ/EN), `patronymic`
- Телефоны (`phone`, `mobilePhone`), `mail`/email
- Адреса (`adress`, `living_adress`, `registration_place`)
- Удостоверение/паспорт: `icnumber`, `icdate`, `passport_*`, `iinplt`, `pincode`
- Банковские реквизиты: `bankId`, `bankAccountNumber`, `iic`, `bic`
- Пароли, хэши, токены, session id, blob-фото (в исходной базе есть — исключить)
- Сертификаты/дипломы с номерами, родители (`student_parents`)

Для скоринга достаточно `StudentID` + перечисленные числовые/категориальные поля.

---

## Итог: минимальный рабочий набор

Чтобы переключить `DATA_SOURCE=platonus` и проверить на реальных данных, достаточно:

1. **`students`** + **`student_info`** + приказы (`orderstudentinfo`,
   `order_section_student_states`) — демография + метка отчисления.
2. **`journal`** (с `week`) + **`totalmarks`** + **`transcript`** — оценки,
   пересдачи, посещаемость (`absence_percentage`), динамика по неделям.
3. **`assignment_recipients`** (с `assessment_week`) — сдачи и сроки.
4. **`ssc_applications`** — академ. отпуск / основания (для метки).
5. Справочники для раскодировки ID.

Дальше эти таблицы прописываются в [data_queries.yaml](data_queries.yaml), и слой
признаков ([features.py](features.py)) собирает из них матрицу без изменений кода.
