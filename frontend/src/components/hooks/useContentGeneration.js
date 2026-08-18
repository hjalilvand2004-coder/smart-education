import { useState, useRef, useCallback } from "react";
import api, { getApiError } from "../../api";
import { getContentBody } from "../ContentExporter";

const DEFAULT_PROVIDER = "openai_compatible";
const DEFAULT_MODEL = "gpt-5.6";
const DEFAULT_LANGUAGE = "fa";

export const useContentGeneration = ({
  safeTopicId,
  onSuccess,
  onError,
}) => {
  const [generating, setGenerating] = useState(false);
  const [provider, setProvider] = useState(DEFAULT_PROVIDER);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [level, setLevel] = useState("intermediate");
  const [contentType, setContentType] = useState("lesson");
  const [customText, setCustomText] = useState("");
  const [manualContent, setManualContent] = useState("");
  const [generationMode, setGenerationMode] = useState("ai");

  const lockRef = useRef(false);

  const generateContent = useCallback(async () => {
    if (lockRef.current || !safeTopicId) return;

    // برای حالت manual نیازی به مدل نیست
    if (generationMode !== "manual") {
      const normalizedModel = String(model || "").trim();
      if (!normalizedModel) {
        onError?.("نام مدل هوش مصنوعی را وارد کنید.");
        return;
      }
    }

    lockRef.current = true;
    setGenerating(true);

    try {
      let response;

      if (generationMode === "manual") {
        // ✅ حالت دستی: استفاده از مسیر /manual با payload مناسب
        const payload = {
          manual_content: String(manualContent || "").trim(),
          title: String(customText || "").trim() || undefined, // عنوان اختیاری
          content_type: contentType,
        };

        if (!payload.manual_content) {
          throw new Error("محتوای دستی نمی‌تواند خالی باشد.");
        }

        response = await api.post(`/content/manual/${safeTopicId}`, payload);
      } else {
        // حالت AI یا Hybrid: استفاده از مسیر /generate
        const payload = {
          topic_id: safeTopicId,
          provider,
          model: String(model || "").trim(),
          language: DEFAULT_LANGUAGE,
          level,
          content_type: contentType,
        };

        if (generationMode === "hybrid") {
          // ترکیبی: custom_text شامل محتوای دستی است
          payload.custom_text = String(manualContent || "").trim() || null;
        } else {
          // AI: فقط custom_text اختیاری
          payload.custom_text = String(customText || "").trim() || null;
        }

        response = await api.post(`/content/generate/${safeTopicId}`, payload);
      }

      const generatedContent = response.data?.content || response.data?.data || response.data;
      if (!generatedContent || typeof generatedContent !== "object") {
        throw new Error("محتوای معتبر از Backend دریافت نشد.");
      }

      const generatedBody = getContentBody(generatedContent);
      if (!generatedBody || !String(generatedBody).trim()) {
        throw new Error("متن محتوای تولیدشده خالی است.");
      }

      onSuccess?.(generatedContent);
    } catch (error) {
      console.error("Content generation error:", error);
      onError?.(getApiError(error));
    } finally {
      lockRef.current = false;
      setGenerating(false);
    }
  }, [safeTopicId, model, provider, level, contentType, customText, manualContent, generationMode, onSuccess, onError]);

  return {
    generating,
    provider,
    setProvider,
    model,
    setModel,
    level,
    setLevel,
    contentType,
    setContentType,
    customText,
    setCustomText,
    manualContent,
    setManualContent,
    generationMode,
    setGenerationMode,
    generateContent,
  };
};