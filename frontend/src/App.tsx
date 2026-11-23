import { BrowserRouter, Navigate, Route, Routes, useParams, useSearchParams } from 'react-router-dom'
import { AuthProvider, useAuth, isGlobalAdmin } from './auth'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Courses from './pages/Courses'
import CourseHome from './pages/CourseHome'
import ContentReader from './pages/ContentReader'
import Studio from './pages/Studio'
import Quiz from './pages/Quiz'
import Assessments from './pages/Assessments'
import Tutor from './pages/Tutor'
import Mastery from './pages/Mastery'
import StudyPlan from './pages/StudyPlan'
import Admin from './pages/Admin'
import Programyar from './pages/Programyar'
import Payehyar from './pages/Payehyar'
import Reports from './pages/Reports'
import SsoCallback from './pages/SsoCallback'
import SmartHub from './pages/SmartHub'
import Today from './pages/Today'
import Learning from './pages/Learning'
import ConceptExplorer from './pages/ConceptExplorer'
import ErrorClinic from './pages/ErrorClinic'
import TeachBack from './pages/TeachBack'
import ExamPrep from './pages/ExamPrep'
import ProfessorActions from './pages/ProfessorActions'

function LoadingScreen({ note = 'در حال بارگذاری…' }: { note?: string }) {
  return (
    <div className="center-note">
      <div className="spinner" />
      {note}
    </div>
  )
}

/** محافظت از مسیرها: بدون ورود → صفحه ورود. */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingScreen note="در حال بررسی ورود…" />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function ContentReaderRoute() {
  const { courseId, versionId } = useParams()
  return <ContentReader courseId={courseId ?? ''} versionId={versionId ?? ''} />
}

function AssessmentsRoute() {
  const { courseId } = useParams()
  return <Assessments courseId={courseId ?? ''} />
}

function TutorRoute() {
  const { courseId } = useParams()
  return <Tutor courseId={courseId ?? ''} />
}

function MasteryRoute() {
  const { courseId } = useParams()
  return <Mastery courseId={courseId ?? ''} />
}

function StudyPlanRoute() {
  const { courseId } = useParams()
  return <StudyPlan courseId={courseId ?? ''} />
}

function SmartHubRoute() {
  const { courseId } = useParams()
  return <SmartHub courseId={courseId ?? ''} />
}

function LearningRoute() {
  const { courseId } = useParams()
  return <Learning courseId={courseId ?? ''} />
}

function ConceptExplorerRoute() {
  const { courseId } = useParams()
  return <ConceptExplorer courseId={courseId ?? ''} />
}

function TeachBackRoute() {
  const { courseId } = useParams()
  return <TeachBack courseId={courseId ?? ''} />
}

function ExamPrepRoute() {
  const { courseId } = useParams()
  return <ExamPrep courseId={courseId ?? ''} />
}

function ProfessorActionsRoute() {
  const { courseId } = useParams()
  return <ProfessorActions courseId={courseId ?? ''} />
}

/** کلینیک خطا: مسیر سراسری با شناسه درس در پارامتر نشانی */
function ErrorClinicRoute() {
  const [params] = useSearchParams()
  return <ErrorClinic courseId={params.get('course_id') ?? ''} />
}

function AdminRoute() {
  const { user } = useAuth()
  if (!isGlobalAdmin(user)) {
    return (
      <div className="empty-box">
        <strong>دسترسی مجاز نیست</strong>
        این بخش فقط برای مدیر آموزشی و مدیر فنی سامانه فعال است.
      </div>
    )
  }
  return <Admin />
}

function NotFound() {
  return (
    <div className="empty-box">
      <strong>صفحه پیدا نشد</strong>
      نشانی واردشده وجود ندارد یا جابه‌جا شده است.
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* لندینگ رویایی: اول زیبایی سایت، بعد ورود — کاربر احرازشده مستقیم وارد می‌شود */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/sso/callback" element={<SsoCallback />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/today" element={<Today />} />
            <Route path="/courses" element={<Courses />} />
            <Route path="/course/:courseId" element={<CourseHome />} />
            <Route path="/course/:courseId/content/:versionId" element={<ContentReaderRoute />} />
            <Route path="/course/:courseId/learn" element={<LearningRoute />} />
            <Route path="/course/:courseId/map" element={<ConceptExplorerRoute />} />
            <Route path="/course/:courseId/quizzes" element={<AssessmentsRoute />} />
            <Route path="/course/:courseId/tutor" element={<TutorRoute />} />
            <Route path="/course/:courseId/mastery" element={<MasteryRoute />} />
            <Route path="/course/:courseId/plan" element={<StudyPlanRoute />} />
            <Route path="/course/:courseId/smart" element={<SmartHubRoute />} />
            <Route path="/course/:courseId/teach-back" element={<TeachBackRoute />} />
            <Route path="/course/:courseId/exam-prep" element={<ExamPrepRoute />} />
            <Route path="/course/:courseId/actions" element={<ProfessorActionsRoute />} />
            <Route path="/me/error-clinic" element={<ErrorClinicRoute />} />
            <Route path="/studio/:courseId" element={<Studio />} />
            <Route path="/programyar" element={<Programyar />} />
            <Route path="/payehyar" element={<Payehyar />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/quiz/:assessmentId" element={<Quiz />} />
            <Route path="/admin" element={<AdminRoute />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
