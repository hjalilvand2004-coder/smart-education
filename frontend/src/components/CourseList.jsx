import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import api, { getApiError } from "../api";


/*
  تبدیل مقدار به عدد صحیح مثبت
*/
const toPositiveInteger = (value) => {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const numberValue = Number(value);

  if (
    !Number.isInteger(numberValue) ||
    numberValue <= 0
  ) {
    return null;
  }

  return numberValue;
};


/*
  شناسه معتبر درس
*/
const getSafeCourseId = (courseId) => {
  return toPositiveInteger(courseId);
};


/*
  استخراج شناسه سرفصل

  نکته بسیار مهم:

  چون پاسخ فعلی Backend این است:

  {
    "id": 1038001,
    "course_id": 1038
  }

  و topic_id وجود ندارد، مقدار id باید بدون
  هیچ تغییری استفاده شود.

  فقط زمانی topic_id استفاده می‌شود که Backend
  آن را صراحتاً ارسال کرده باشد.
*/
const getSafeTopicId = (topic) => {
  if (!topic || typeof topic !== "object") {
    return null;
  }

  const explicitTopicId =
    topic.topic_id ??
    topic.topicId ??
    topic.real_topic_id;

  const safeExplicitTopicId =
    toPositiveInteger(explicitTopicId);

  if (safeExplicitTopicId) {
    return safeExplicitTopicId;
  }

  /*
    در پاسخ فعلی، این مقدار مثلاً 1038001 است.
    نباید به 1 تبدیل شود.
  */
  return toPositiveInteger(topic.id);
};


/*
  ساخت شیء استاندارد سرفصل
*/
const normalizeTopic = (topic, fallbackCourseId) => {
  if (!topic || typeof topic !== "object") {
    return null;
  }

  const topicId = getSafeTopicId(topic);

  if (!topicId) {
    return null;
  }

  const courseId = getSafeCourseId(
    topic.course_id ??
      topic.courseId ??
      fallbackCourseId
  );

  return {
    ...topic,

    /*
      این دو مقدار برابر شناسه واقعی رکورد
      در دیتابیس هستند؛ مثلاً 1038001
    */
    id: topicId,
    topic_id: topicId,

    course_id: courseId,
  };
};


function CourseList({
  courseId,
  refreshKey = 0,
  selectedTopicId = null,
  onSelectTopic,
}) {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchText, setSearchText] =
    useState("");
  const [showOnlyActive, setShowOnlyActive] =
    useState(false);


  const safeCourseId = useMemo(() => {
    return getSafeCourseId(courseId);
  }, [courseId]);


  const safeSelectedTopicId = useMemo(() => {
    return toPositiveInteger(selectedTopicId);
  }, [selectedTopicId]);


  /*
    بررسی وضعیت فعال بودن سرفصل
  */
  const isTopicActive = useCallback((topic) => {
    const value =
      topic?.is_active ??
      topic?.active ??
      topic?.status;

    return (
      value === true ||
      value === 1 ||
      value === "1" ||
      value === "true" ||
      value === "True" ||
      value === "active" ||
      value === "فعال"
    );
  }, []);


  /*
    استخراج سرفصل‌ها از همه ساختارهای
    محتمل پاسخ Backend

    پاسخ فعلی شما:
    {
      "value": [...]
    }
  */
  const extractTopics = useCallback(
    (responseData) => {
      if (Array.isArray(responseData)) {
        return responseData;
      }

      if (Array.isArray(responseData?.value)) {
        return responseData.value;
      }

      if (Array.isArray(responseData?.topics)) {
        return responseData.topics;
      }

      if (Array.isArray(responseData?.items)) {
        return responseData.items;
      }

      if (Array.isArray(responseData?.data)) {
        return responseData.data;
      }

      if (Array.isArray(responseData?.results)) {
        return responseData.results;
      }

      return [];
    },
    []
  );


  /*
    بررسی تعلق سرفصل به درس انتخاب‌شده
  */
  const belongsToCurrentCourse = useCallback(
    (topic) => {
      if (!topic || !safeCourseId) {
        return false;
      }

      const topicCourseId =
        toPositiveInteger(
          topic.course_id ??
            topic.courseId
        );

      /*
        اگر course_id در پاسخ وجود نداشت،
        فعلاً سرفصل را حذف نمی‌کنیم.
      */
      if (!topicCourseId) {
        return true;
      }

      return topicCourseId === safeCourseId;
    },
    [safeCourseId]
  );


  /*
    دریافت سرفصل‌ها
  */
  const loadTopics = useCallback(
    async (signal) => {
      if (!safeCourseId) {
        setTopics([]);
        setError("");
        return;
      }

      try {
        setLoading(true);
        setError("");

        const response = await api.get(
          `/courses/${safeCourseId}/topics`,
          {
            signal,
          }
        );

        const receivedTopics =
          extractTopics(response?.data);

        const normalizedTopics =
          receivedTopics
            .filter((topic) =>
              belongsToCurrentCourse(topic)
            )
            .map((topic) =>
              normalizeTopic(
                topic,
                safeCourseId
              )
            )
            .filter(Boolean);

        setTopics(normalizedTopics);

        console.log(
          "CourseList response:",
          response?.data
        );

        console.log(
          "Normalized topics:",
          normalizedTopics
        );
      } catch (requestError) {
        const canceled =
          requestError?.code ===
            "ERR_CANCELED" ||
          requestError?.name ===
            "CanceledError" ||
          requestError?.name ===
            "AbortError";

        if (canceled) {
          return;
        }

        setTopics([]);

        setError(
          String(
            getApiError(requestError) ||
              "دریافت سرفصل‌ها با خطا مواجه شد."
          )
        );
      } finally {
        setLoading(false);
      }
    },
    [
      safeCourseId,
      extractTopics,
      belongsToCurrentCourse,
    ]
  );


  /*
    بارگذاری اولیه و بارگذاری مجدد
  */
  useEffect(() => {
    const controller =
      new AbortController();

    loadTopics(controller.signal);

    return () => {
      controller.abort();
    };
  }, [loadTopics, refreshKey]);


  /*
    پاک‌سازی فیلترها با تغییر درس
  */
  useEffect(() => {
    setSearchText("");
    setShowOnlyActive(false);
    setError("");
  }, [safeCourseId]);


  /*
    فیلتر و مرتب‌سازی
  */
  const filteredTopics = useMemo(() => {
    const normalizedSearch =
      searchText.trim().toLowerCase();

    return [...topics]
      .filter((topic) => {
        if (!showOnlyActive) {
          return true;
        }

        return isTopicActive(topic);
      })
      .filter((topic) => {
        if (!normalizedSearch) {
          return true;
        }

        const searchableText = [
          topic?.id,
          topic?.topic_id,
          topic?.title,
          topic?.name,
          topic?.description,
          topic?.course_id,
          topic?.sort_order,
        ]
          .filter(
            (value) =>
              value !== null &&
              value !== undefined
          )
          .join(" ")
          .toLowerCase();

        return searchableText.includes(
          normalizedSearch
        );
      })
      .sort((first, second) => {
        const firstOrder = Number(
          first?.sort_order ??
            first?.order ??
            0
        );

        const secondOrder = Number(
          second?.sort_order ??
            second?.order ??
            0
        );

        if (firstOrder !== secondOrder) {
          return firstOrder - secondOrder;
        }

        return Number(first.id) - Number(second.id);
      });
  }, [
    topics,
    searchText,
    showOnlyActive,
    isTopicActive,
  ]);


  /*
    انتخاب سرفصل

    در وضعیت فعلی، اگر id برابر 1038001 باشد،
    دقیقاً همان 1038001 به App ارسال می‌شود.
  */
  const handleSelectTopic = useCallback(
    (topic) => {
      const normalizedTopic =
        normalizeTopic(
          topic,
          safeCourseId
        );

      if (!normalizedTopic) {
        setError(
          "شناسه سرفصل معتبر نیست."
        );
        return;
      }

      console.log(
        "Selected topic sent to App:",
        normalizedTopic
      );

      if (
        typeof onSelectTopic === "function"
      ) {
        onSelectTopic(normalizedTopic);
      }
    },
    [safeCourseId, onSelectTopic]
  );


  /*
    درسی انتخاب نشده است
  */
  if (!safeCourseId) {
    return (
      <section
        className="card topics-card topics-empty-course"
        dir="rtl"
      >
        <div className="empty-state">
          <div className="empty-state-icon">
            📚
          </div>

          <h3>درسی انتخاب نشده است</h3>

          <p>
            ابتدا یک درس را انتخاب کنید تا
            سرفصل‌های آن نمایش داده شود.
          </p>
        </div>
      </section>
    );
  }


  return (
    <section
      className="card topics-card"
      dir="rtl"
    >
      <div className="section-header topics-section-header">
        <div>
          <span className="section-kicker">
            مدیریت آموزشی
          </span>

          <h2>فهرست سرفصل‌های درس</h2>

          <p className="section-description">
            برای تولید محتوای آموزشی یا ساخت آزمون،
            سرفصل موردنظر را انتخاب کنید.
          </p>
        </div>

        <button
          type="button"
          className="secondary-button"
          onClick={() => loadTopics()}
          disabled={loading}
        >
          {loading ? (
            <>
              <span
                className="button-spinner blue"
                aria-hidden="true"
              />

              در حال دریافت...
            </>
          ) : (
            <>
              <span aria-hidden="true">
                ↻
              </span>

              به‌روزرسانی
            </>
          )}
        </button>
      </div>


      {!loading && topics.length > 0 && (
        <div className="topics-toolbar">
          <div className="topics-search">
            <label htmlFor="topic-search">
              جست‌وجوی سرفصل
            </label>

            <input
              id="topic-search"
              type="search"
              value={searchText}
              onChange={(event) =>
                setSearchText(
                  event.target.value
                )
              }
              placeholder="عنوان، شناسه یا توضیح سرفصل..."
            />
          </div>

          <div className="topics-toolbar-actions">
            <span className="topics-count">
              نمایش {filteredTopics.length} از{" "}
              {topics.length}
            </span>

            <label className="active-filter">
              <input
                type="checkbox"
                checked={showOnlyActive}
                onChange={(event) =>
                  setShowOnlyActive(
                    event.target.checked
                  )
                }
              />

              فقط فعال‌ها
            </label>
          </div>
        </div>
      )}


      {error && (
        <div
          className="content-message error topics-error"
          role="alert"
        >
          <span aria-hidden="true">!</span>

          <p>{error}</p>

          <button
            type="button"
            className="message-close"
            onClick={() => setError("")}
            aria-label="بستن پیام خطا"
          >
            ×
          </button>
        </div>
      )}


      {loading && (
        <div className="loading-box topics-loading">
          <div
            className="spinner"
            aria-hidden="true"
          />

          <span>
            در حال دریافت سرفصل‌ها...
          </span>
        </div>
      )}


      {!loading &&
        topics.length === 0 &&
        !error && (
          <div className="empty-state compact">
            <div className="empty-state-icon">
              📋
            </div>

            <h3>سرفصلی ثبت نشده است</h3>

            <p>
              ابتدا فایل Excel یا CSV سرفصل‌ها
              را بارگذاری کنید.
            </p>
          </div>
        )}


      {!loading &&
        topics.length > 0 &&
        filteredTopics.length === 0 && (
          <div className="empty-state compact">
            <div className="empty-state-icon">
              🔎
            </div>

            <h3>نتیجه‌ای پیدا نشد</h3>

            <p>
              عبارت جست‌وجو یا فیلتر وضعیت را
              تغییر دهید.
            </p>

            <button
              type="button"
              className="light-action"
              onClick={() => {
                setSearchText("");
                setShowOnlyActive(false);
              }}
            >
              پاک‌کردن فیلترها
            </button>
          </div>
        )}


      {!loading &&
        filteredTopics.length > 0 && (
          <div className="table-wrapper">
            <table className="topics-table">
              <thead>
                <tr>
                  <th>ردیف</th>
                  <th>شناسه سرفصل</th>
                  <th>شناسه درس</th>
                  <th>عنوان سرفصل</th>
                  <th>شرح سرفصل</th>
                  <th>مدت جلسه</th>
                  <th>ترتیب</th>
                  <th>وضعیت</th>
                  <th>عملیات</th>
                </tr>
              </thead>

              <tbody>
                {filteredTopics.map(
                  (topic, index) => {
                    const topicId =
                      getSafeTopicId(topic);

                    const isSelected =
                      safeSelectedTopicId ===
                      topicId;

                    const active =
                      isTopicActive(topic);

                    return (
                      <tr
                        key={`topic-${topicId}`}
                        className={
                          isSelected
                            ? "selected-row"
                            : ""
                        }
                        onClick={() =>
                          handleSelectTopic(
                            topic
                          )
                        }
                        tabIndex={0}
                        onKeyDown={(event) => {
                          if (
                            event.key ===
                              "Enter" ||
                            event.key === " "
                          ) {
                            event.preventDefault();

                            handleSelectTopic(
                              topic
                            );
                          }
                        }}
                      >
                        <td>
                          <span className="row-number">
                            {index + 1}
                          </span>
                        </td>

                        <td>
                          <span className="id-badge">
                            {topicId}
                          </span>
                        </td>

                        <td>
                          <span className="course-id">
                            {topic.course_id ??
                              safeCourseId}
                          </span>
                        </td>

                        <td className="title-cell">
                          <strong>
                            {topic.title ||
                              topic.name ||
                              "بدون عنوان"}
                          </strong>
                        </td>

                        <td className="description-cell">
                          {topic.description ? (
                            <span
                              title={String(
                                topic.description
                              )}
                            >
                              {topic.description}
                            </span>
                          ) : (
                            <span className="muted-text">
                              توضیحی ثبت نشده است
                            </span>
                          )}
                        </td>

                        <td>
                          <span className="duration-badge">
                            ⏱{" "}
                            {topic.session_minute ??
                              topic.duration ??
                              "—"}{" "}
                            دقیقه
                          </span>
                        </td>

                        <td>
                          <span className="sort-badge">
                            {topic.sort_order ??
                              topic.order ??
                              "—"}
                          </span>
                        </td>

                        <td>
                          <span
                            className={
                              active
                                ? "active-badge"
                                : "inactive-badge"
                            }
                          >
                            {active
                              ? "فعال"
                              : "غیرفعال"}
                          </span>
                        </td>

                        <td>
                          <button
                            type="button"
                            className={
                              isSelected
                                ? "select-button selected"
                                : "select-button"
                            }
                            onClick={(event) => {
                              event.stopPropagation();

                              handleSelectTopic(
                                topic
                              );
                            }}
                          >
                            {isSelected
                              ? "انتخاب شد ✓"
                              : "انتخاب سرفصل"}
                          </button>
                        </td>
                      </tr>
                    );
                  }
                )}
              </tbody>
            </table>
          </div>
        )}


      {safeSelectedTopicId && (
        <div className="table-footer-message">
          <span aria-hidden="true">✓</span>

          <p>
            سرفصل با شناسه{" "}
            <strong>
              {safeSelectedTopicId}
            </strong>{" "}
            انتخاب شده است. اکنون می‌توانید
            از بخش تولید محتوا یا آزمون استفاده
            کنید.
          </p>
        </div>
      )}
    </section>
  );
}


export default CourseList;