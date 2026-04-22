import os
import torch
import torch.nn as nn
import torchaudio
import numpy as np
from transformers import Wav2Vec2FeatureExtractor, WavLMModel

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
SAMPLE_RATE = 16000
CREMA_D_DURATION = 3.0
NUM_SAMPLES = int(SAMPLE_RATE * CREMA_D_DURATION)

class wavLMModel(nn.Module):
    def __init__(self, num_classes, num_finetune_layers=6, dropout=0.3):
        super().__init__()
        self.wavlm = WavLMModel.from_pretrained("microsoft/wavlm-base-plus")
        self.num_finetune_layers = num_finetune_layers
        self.dropout = dropout
        self.wavlm_hidden_size = self.wavlm.config.hidden_size

        self._setup_selective_finetuning()

        self.feature_network = nn.Sequential(
            nn.Linear(self.wavlm_hidden_size, self.wavlm_hidden_size // 2),
            nn.LayerNorm(self.wavlm_hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(self.wavlm_hidden_size // 2, self.wavlm_hidden_size // 4),
            nn.LayerNorm(self.wavlm_hidden_size // 4),
            nn.ReLU(),
            nn.Dropout(dropout / 2)
        )

        self.classifier = nn.Linear(self.wavlm_hidden_size // 4, num_classes)
        self._initialize_weights()

    def _setup_selective_finetuning(self):
        for param in self.wavlm.parameters():
            param.requires_grad = False
        wavlm_layers = self.wavlm.encoder.layers
        for i in range(len(wavlm_layers) - self.num_finetune_layers, len(wavlm_layers)):
            for param in wavlm_layers[i].parameters():
                param.requires_grad = True

    def _initialize_weights(self):
        for layer in self.feature_network:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_normal_(layer.weight)
                if layer.bias is not None:
                    nn.init.zeros_(layer.bias)
        if isinstance(self.classifier, nn.Linear):
            nn.init.xavier_normal_(self.classifier.weight)
            if self.classifier.bias is not None:
                nn.init.zeros_(self.classifier.bias)

    def forward(self, input_values):
        wavlm_outputs = self.wavlm(input_values)
        wavlm_features = torch.mean(wavlm_outputs.last_hidden_state, dim=1)
        processed_features = self.feature_network(wavlm_features)
        logits = self.classifier(processed_features)
        return logits


class SERInference:
    def __init__(self, model_path="models/ser/wavlm_optimized_seed42.pth"):
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

            self.model = wavLMModel(
                num_classes=model_config['num_classes'],
                num_finetune_layers=model_config['num_finetune_layers'],
                dropout=model_config['dropout']
            )
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.to(self.device)
            self.model.eval()
            print(f"[SER] Loaded model with classes: {self.label_classes}")
        except Exception as e:
            print(f"[SER] Failed to load model: {e}")
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
                logits = self.model(input_values)
                pred_idx = torch.argmax(logits, dim=1).item()
                emotion = self.label_classes[pred_idx] if self.label_classes else str(pred_idx)
            return emotion.capitalize()
        except Exception as e:
            print(f"[SER] Inference error: {e}")
            return "Error"
