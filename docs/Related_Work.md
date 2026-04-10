# Related Work

Our system sits at the intersection of five active research areas: facial/video emotion recognition, speech emotion recognition, physiological signal-based affect detection, multimodal fusion, and LLM-driven adaptive systems for mental health. The following sections survey the most relevant prior work in each area.

---

## 1. Facial and Video-Based Emotion Recognition

The foundation of automated facial emotion recognition (FER) was systematically laid by **Mollahosseini et al. (2019)** [1], who introduced AffectNet — the largest in-the-wild facial expression dataset, with over one million images annotated for seven discrete emotions and continuous valence/arousal dimensions. They trained ResNet-based CNN baselines and showed deep networks dramatically outperform classical machine learning, while also establishing that real-world variation (pose, occlusion, lighting) is the central challenge. AffectNet is the definitive benchmark our facial module is evaluated against.

A comprehensive landscape of FER architectures is provided by the survey of **Li and Deng (2022)** [2], which reviews datasets (FER2013, AffectNet, RAF-DB), backbone choices (CNNs, GANs, graph networks, Vision Transformers), and training strategies for handling label noise and class imbalance. Their taxonomy of static-image vs. dynamic video-based FER directly informs our design decisions around frame-level vs. temporal modeling.

An important extension beyond face-only recognition is presented by **Kosti et al. (2017)** [3] in their EMOTIC model (CVPR 2017). They demonstrate that jointly analyzing the person's face/body *and* the surrounding scene context — via a two-branch CNN — significantly improves emotion prediction across 26 discrete categories and the valence/arousal/dominance dimensions. In a therapy setting where faces may be partially occluded or non-frontal, scene context becomes a valuable supplementary signal, motivating context-aware architectures.

---

## 2. Speech and Voice Emotion Recognition (SER)

The state of the art in SER has shifted decisively toward self-supervised transformer models. **Baevski et al. (2020)** [4] introduced **wav2vec 2.0** (NeurIPS 2020), a framework that learns powerful speech representations by masking raw audio and training a quantized contrastive objective. Fine-tuned wav2vec 2.0 models achieve top results on IEMOCAP and RAVDESS — the primary SER benchmarks — and offer a compelling alternative to hand-crafted Mel-Spectrogram + CNN pipelines by capturing prosodic and paralinguistic features directly from the waveform.

Building on this, **Hsu et al. (2021)** [5] proposed **HuBERT**, which uses BERT-inspired masked prediction over iteratively refined cluster pseudo-labels. HuBERT's representations better capture tonal and rhythmic content relevant to emotion, making it the leading backbone for speaker-independent SER — the harder and more clinically realistic condition for our therapy application.

A systematic comparison of these SSL backbones — wav2vec 2.0, HuBERT, WavLM, data2vec — for SER is provided by **Fan et al. (2022)** [6] (ICASSP 2022). Their study shows SSL models consistently outperform Mel-Spectrogram CNN baselines, and that lightweight distilled variants retain strong performance at a fraction of the inference cost, directly addressing the real-time deployment trade-off in our system.

---

## 3. Physiological / Biometric Signal Emotion Recognition

The canonical benchmark for EDA and PPG-based emotion recognition is **DEAP**, introduced by **Koelstra et al. (2012)** [7]. EEG and peripheral physiological signals (including GSR/EDA and blood volume pulse/PPG) were recorded from 32 participants watching music videos, with self-reported valence, arousal, dominance, and liking ratings. DEAP defines both the signal modalities and the dimensional emotion labels our biometric module targets, and virtually every EDA/PPG paper evaluates on it.

A more ecologically valid wearable benchmark is **WESAD**, introduced by **Schmidt et al. (2018)** [8] (ACM ICMI 2018). It collects chest- and wrist-based EDA, PPG, ECG, EMG, temperature, and respiration from 15 subjects under neutral, stress, and amusement conditions induced via the Trier Social Stress Test. WESAD establishes that multimodal physiological fusion outperforms any single-channel approach and defines the leave-one-subject-out evaluation protocol our system should adopt to demonstrate real-world generalization.

The specific pipeline our biometric module implements — converting EDA/ECG signals into 2D scalogram images via Continuous Wavelet Transform (CWT) and feeding them to pretrained CNNs — is validated by **On et al. (2023)** [9]. Their paper applies CWT scalograms with InceptionResNetV2, MobileNet, and VGG classifiers on DEAP, achieving up to 99.19% valence accuracy with MobileNet. This directly confirms the feasibility of our scalogram + vision model approach and justifies the choice of CWT over simpler time-frequency representations.

---

## 4. Multimodal Emotion Fusion

Fusing signals from misaligned temporal streams (video frames at 30 fps, audio windows, slow physiological signals) is the core architectural challenge in multimodal emotion systems. **Tsai et al. (2019)** [10] addressed this with the **Multimodal Transformer (MulT)** (ACL 2019), which uses directed pairwise cross-modal attention to continuously integrate audio, visual, and text features without requiring temporal alignment. MulT is the foundational transformer-based fusion architecture in our field and directly motivates the cross-modal attention design in our fusion module.

A more recent advance is **TDFNet (2023)** [11], which proposes a hierarchical multi-scale transformer fusion approach that extracts features at multiple temporal granularities per modality and achieves state-of-the-art on CMU-MOSI and CMU-MOSEI. TDFNet's multi-scale design is particularly important for our system, where physiological signals and speech naturally operate at very different temporal scales.

The broader landscape of deep learning multimodal emotion recognition combining speech, text, and face is surveyed by **Zhu et al. (2023)** [12], covering over 100 papers across feature extraction methods (CNN, RNN, Transformer), fusion strategies (early, late, model-level, hybrid), and open problems including missing modality handling. Critically, the survey identifies that physiological signals (EDA/PPG) are underrepresented in the dominant audio-visual-text paradigm — a gap our system directly addresses by incorporating a biometric modality.

---

## 5. Affective Computing for Mental Health and LLM-Driven Adaptation

The theoretical grounding for all of the above rests on Picard's foundational monograph **Affective Computing (1997)** [13], which coined the term and defined the research agenda: building systems that recognize, interpret, and simulate human emotions using physiological biosignals (EDA, heart rate, muscle tension). Picard's proposed valence-arousal-dominance representation and her vision of machines that respond adaptively to human emotional context are the direct ancestors of every component in our system.

The current state and future directions of the field are mapped by **Zhang et al. (2023)** [14] in a high-impact review published in *Intelligent Computing* (AAAS). This review covers the full stack from signal modalities and deep learning architectures to LLM-augmented affective systems, specifically arguing that LLMs provide the reasoning and language generation capacity needed to move from emotion *detection* to adaptive emotional *response* — precisely what our LLM-driven orchestration layer does.

The closest architectural precedent to our LLM integration is the work of **Wang et al. (2024)** [15], who present a complete system where an LLM-powered conversational agent delivers CBT-aligned psychotherapeutic interventions through smart devices, using real-time affect detection to inject an emotion vector into the LLM's prompt. Their study shows that emotion-aware prompt injection significantly improves the empathic quality and clinical appropriateness of LLM responses compared to emotion-blind baselines. This validates our closed-loop design of feeding real-time emotion classifications from the multimodal module directly into the LLM's context for adaptive scenario control.

---

## References

[1] A. Mollahosseini, B. Hasani, and M. H. Mahoor, "AffectNet: A Database for Facial Expression, Valence, and Arousal Computing in the Wild," *IEEE Transactions on Affective Computing*, vol. 10, no. 1, pp. 18–31, 2019. https://doi.org/10.1109/TAFFC.2017.2740923

[2] S. Li and W. Deng, "Deep Facial Expression Recognition: A Survey," *IEEE Transactions on Affective Computing*, vol. 13, no. 3, pp. 1195–1215, 2022. https://doi.org/10.1109/TAFFC.2020.2981446

[3] R. Kosti, J. M. Alvarez, A. Recasens, and A. Lapedriza, "Emotion Recognition in Context," in *Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*, 2017. https://openaccess.thecvf.com/content_cvpr_2017/html/Kosti_Emotion_Recognition_in_CVPR_2017_paper.html

[4] A. Baevski, Y. Zhou, A. Mohamed, and M. Auli, "wav2vec 2.0: A Framework for Self-Supervised Learning of Speech Representations," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 33, 2020. https://arxiv.org/abs/2006.11477

[5] W.-N. Hsu, B. Bolte, Y.-H. H. Tsai, K. Lakhotia, R. Salakhutdinov, and A. Mohamed, "HuBERT: Self-Supervised Speech Representation Learning by Masked Prediction of Hidden Units," *IEEE/ACM Transactions on Audio, Speech, and Language Processing*, vol. 29, pp. 3451–3460, 2021. https://doi.org/10.1109/TASLP.2021.3122291

[6] Z. Fan, M. Li, S. Zhou, and B. Xu, "Speech Emotion Recognition Using Self-Supervised Features," in *Proc. IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)*, 2022. https://arxiv.org/abs/2202.03896

[7] S. Koelstra et al., "DEAP: A Database for Emotion Analysis Using Physiological Signals," *IEEE Transactions on Affective Computing*, vol. 3, no. 1, pp. 18–31, 2012. https://doi.org/10.1109/T-AFFC.2011.15

[8] P. Schmidt, A. Reiss, R. Duerichen, C. Marberger, and K. Van Laerhoven, "Introducing WESAD, a Multimodal Dataset for Wearable Stress and Affect Detection," in *Proc. 20th ACM International Conference on Multimodal Interaction (ICMI)*, 2018. https://doi.org/10.1145/3242969.3242985

[9] K.-W. On, H.-Y. Kim et al., "Emotion Classification Based on CWT of ECG and GSR Signals Using Various CNN Models," *Electronics*, vol. 12, no. 13, article 2795, 2023. https://doi.org/10.3390/electronics12132795

[10] Y.-H. H. Tsai, S. Bai, P. P. Liang, J. Z. Kolter, L.-P. Morency, and R. Salakhutdinov, "Multimodal Transformer for Unaligned Multimodal Language Sequences," in *Proc. 57th Annual Meeting of the Association for Computational Linguistics (ACL)*, pp. 6558–6569, 2019. https://aclanthology.org/P19-1656

[11] Y. Zhao et al., "TDFNet: Transformer-Based Deep-Scale Fusion Network for Multimodal Emotion Recognition," *IEEE/ACM Transactions on Audio, Speech and Language Processing*, vol. 31, 2023. https://doi.org/10.1109/TASLP.2023.3316458

[12] Y. Zhu et al., "A Survey of Deep Learning-Based Multimodal Emotion Recognition: Speech, Text, and Face," *Electronics*, vol. 12, no. 20, article 4279, 2023. https://pmc.ncbi.nlm.nih.gov/articles/PMC10606253/

[13] R. W. Picard, *Affective Computing*. MIT Press, 1997. ISBN: 9780262661157.

[14] X. Zhang et al., "Affective Computing: Recent Advances, Challenges, and Future Trends," *Intelligent Computing* (AAAS), 2023. https://doi.org/10.34133/icomputing.0076

[15] H. Wang et al., "LLM-based Conversational AI Therapist for Daily Functioning Screening and Psychotherapeutic Intervention via Everyday Smart Devices," *ACM Transactions on Computing for Healthcare*, 2024. https://doi.org/10.1145/3712299
