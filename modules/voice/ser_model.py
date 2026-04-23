import os
import torch
import torch.nn as nn
import torchaudio
import numpy as np
from transformers import Wav2Vec2FeatureExtractor, WavLMModel, HubertModel

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
SAMPLE_RATE = 16000
CREMA_D_DURATION = 3.0
NUM_SAMPLES = int(SAMPLE_RATE * CREMA_D_DURATION)


class WavLMHubertFusionModel(nn.Module):
    def __init__(self, num_classes, num_finetune_layers=11, dropout=0.3):
        super().__init__()
        self.wavlm = WavLMModel.from_pretrained("microsoft/wavlm-base-plus")
        self.hubert = HubertModel.from_pretrained("facebook/hubert-base-ls960")
        self.num_finetune_layers = num_finetune_layers
        self.dropout = dropout

        wavlm_hidden = self.wavlm.config.hidden_size  # 768
        hubert_hidden = self.hubert.config.hidden_size  # 768

        self._setup_selective_finetuning()

        self.wavlm_proj = nn.Linear(wavlm_hidden, wavlm_hidden)
        self.hubert_proj = nn.Linear(hubert_hidden, hubert_hidden)

        combined_dim = wavlm_hidden + hubert_hidden  # 1536

        self.attention_gate = nn.Sequential(
            nn.Linear(combined_dim, 2),
            nn.Sigmoid()
        )

        self.fusion_network = nn.Sequential(
            nn.Linear(combined_dim, wavlm_hidden),       # 1536 -> 768
            nn.LayerNorm(wavlm_hidden),                    # 768
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(wavlm_hidden, wavlm_hidden // 2),   # 768 -> 384
            nn.LayerNorm(wavlm_hidden // 2),               # 384
            nn.ReLU(),
            nn.Dropout(dropout / 2)
        )

        self.classifier = nn.Linear(wavlm_hidden // 2, num_classes)  # 384 -> 8
        self._initialize_weights()

    def _setup_selective_finetuning(self):
        for param in self.wavlm.parameters():
            param.requires_grad = False
        wavlm_layers = self.wavlm.encoder.layers
        for i in range(len(wavlm_layers) - self.num_finetune_layers, len(wavlm_layers)):
            for param in wavlm_layers[i].parameters():
                param.requires_grad = True

        for param in self.hubert.parameters():
            param.requires_grad = False
        hubert_layers = self.hubert.encoder.layers
        for i in range(len(hubert_layers) - self.num_finetune_layers, len(hubert_layers)):
            for param in hubert_layers[i].parameters():
                param.requires_grad = True

    def _initialize_weights(self):
        for module in [self.wavlm_proj, self.hubert_proj, self.classifier]:
            if isinstance(module, nn.Linear):
                nn.init.xavier_normal_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
        for layer in self.fusion_network:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_normal_(layer.weight)
                if layer.bias is not None:
                    nn.init.zeros_(layer.bias)
        for layer in self.attention_gate:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_normal_(layer.weight)
                if layer.bias is not None:
                    nn.init.zeros_(layer.bias)

    def forward(self, wavlm_input, hubert_input):
        wavlm_outputs = self.wavlm(wavlm_input)
        wavlm_features = torch.mean(wavlm_outputs.last_hidden_state, dim=1)
        wavlm_proj = self.wavlm_proj(wavlm_features)

        hubert_outputs = self.hubert(hubert_input)
        hubert_features = torch.mean(hubert_outputs.last_hidden_state, dim=1)
        hubert_proj = self.hubert_proj(hubert_features)

        combined = torch.cat([wavlm_proj, hubert_proj], dim=-1)  # [batch, 1536]
        gate = self.attention_gate(combined)  # [batch, 2]

        wavlm_weight = gate[:, 0:1]  # [batch, 1]
        hubert_weight = gate[:, 1:2]  # [batch, 1]

        weighted_wavlm = wavlm_proj * wavlm_weight
        weighted_hubert = hubert_proj * hubert_weight
        gated_combined = torch.cat([weighted_wavlm, weighted_hubert], dim=-1)  # [batch, 1536]

        fused = self.fusion_network(gated_combined)  # [batch, 384]
        logits = self.classifier(fused)  # [batch, 8]
        return logits


class SERInference:
    def __init__(self, model_path="models/ser/wavlm_hubert_optimized_seed42.pth"):
        self.model_path = model_path
        self.model = None
        self.feature_extractor = None
        self.label_classes = None
        self.device = DEVICE
        self._load_model()

    def _load_model(self):
        if not os.path.exists(self.model_path):
            print(f"[SER] Model not found at {self.model_path}. SER will be unavailable.")
            return

        try:
            checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=False)
            model_config = checkpoint['model_config']
            self.label_classes = checkpoint['label_encoder_classes']

            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained("microsoft/wavlm-base-plus")

            self.model = WavLMHubertFusionModel(
                num_classes=model_config['num_classes'],
                num_finetune_layers=model_config['num_finetune_layers'],
                dropout=model_config['dropout']
            )
            self.model.load_state_dict(checkpoint['model_state_dict'], strict=True)
            self.model.to(self.device)
            self.model.eval()
            print(f"[SER] Loaded fusion model with classes: {self.label_classes}")
        except Exception as e:
            print(f"[SER] Failed to load fusion model: {e}")
            self.model = None

    def predict(self, waveform_np, sr=SAMPLE_RATE):
        if self.model is None or self.feature_extractor is None:
            return "Unavailable"

        try:
            waveform = torch.from_numpy(waveform_np).float()
            if waveform.ndim > 1:
                waveform = waveform.mean(dim=0)

            if sr != SAMPLE_RATE:
                resampler = torchaudio.transforms.Resample(sr, SAMPLE_RATE)
                waveform = resampler(waveform)

            if waveform.shape[0] < NUM_SAMPLES:
                waveform = torch.nn.functional.pad(waveform, (0, NUM_SAMPLES - waveform.shape[0]))
            else:
                waveform = waveform[:NUM_SAMPLES]

            inputs = self.feature_extractor(
                waveform.numpy(),
                sampling_rate=SAMPLE_RATE,
                return_tensors="pt",
                padding=True
            )
            input_values = inputs['input_values'].to(self.device)

            with torch.no_grad():
                logits = self.model(input_values, input_values)
                probs = torch.softmax(logits, dim=1)
                confidence, pred_idx = torch.max(probs, dim=1)
                confidence = confidence.item()
                pred_idx = pred_idx.item()
                emotion = self.label_classes[pred_idx] if self.label_classes else str(pred_idx)
            return emotion.capitalize(), confidence
        except Exception as e:
            print(f"[SER] Inference error: {e}")
            return "Error", 0.0

    def predict_batch(self, waveform_np, sr=SAMPLE_RATE, chunk_size=NUM_SAMPLES, hop_size=None, min_confidence=0.30):
        if hop_size is None:
            hop_size = chunk_size // 2

        if self.model is None or self.feature_extractor is None:
            return "Unavailable", {}, 0.0

        if waveform_np.ndim > 1:
            waveform_np = waveform_np.mean(axis=1)
        waveform_np = waveform_np.astype(np.float32)

        if sr != SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(sr, SAMPLE_RATE)
            waveform_np = resampler(torch.from_numpy(waveform_np)).numpy()
            sr = SAMPLE_RATE

        if len(waveform_np) < int(SAMPLE_RATE * 0.5):
            return "Neutral", {}, 0.0

        emotion_weights = {}
        total_confidence = 0.0

        i = 0
        while i + chunk_size <= len(waveform_np):
            chunk = waveform_np[i:i + chunk_size]
            emotion, conf = self.predict(chunk, sr=sr)
            if conf >= min_confidence and emotion not in ("Unavailable", "Error"):
                emotion_weights[emotion] = emotion_weights.get(emotion, 0.0) + conf
                total_confidence += conf
            i += hop_size

        if len(waveform_np) < chunk_size:
            padded = np.zeros(chunk_size, dtype=np.float32)
            padded[:len(waveform_np)] = waveform_np
            emotion, conf = self.predict(padded, sr=sr)
            if conf >= min_confidence and emotion not in ("Unavailable", "Error"):
                emotion_weights[emotion] = emotion_weights.get(emotion, 0.0) + conf * 0.5
                total_confidence += conf * 0.5

        if not emotion_weights:
            return "Neutral", {}, 0.0

        dominant = max(emotion_weights, key=emotion_weights.get)
        return dominant, emotion_weights, total_confidence / len(emotion_weights)