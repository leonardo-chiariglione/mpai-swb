using System;
using System.Collections.Generic;
using System.Linq;

using Mpai.Core;

namespace Mpai.Hci.Idr;

// ---------------------------------------------------------------------------
//  ID Reconciliation AIM (HCI-IDR).  "Plain C# fusion over FIR/SIR; no model;
//  the work is policy." (M3154)
//
//  Reconciles the face-identity evidence (FIR) and speaker-identity evidence
//  (SIR) for ONE person - whom AVA has associated across the two modalities -
//  into a single reconciled identity. Score-level biometric fusion:
//
//    1. Each modality gives a score VECTOR over the common subject space
//       (SubjectGallery): FIR -> (subject, faceCos)[], SIR -> (subject, voiceCos)[].
//    2. NORMALISE each vector (min-max to [0,1]) so face-cosines and
//       voice-cosines are comparable before combining - the step biometric-
//       fusion literature flags as essential (raw cosine ranges differ by
//       modality; without this one modality dominates).
//    3. FUSE per subject: weighted sum  w*face + (1-w)*voice  over the UNION of
//       subjects. A subject scored by only one modality keeps that modality's
//       (weighted) score - so a missing modality degrades gracefully rather than
//       zeroing the subject. (Weighted sum, not product: it survives one absent
//       or near-zero modality, which a real system needs. Product/naive-Bayes is
//       available as an alternative rule.)
//    4. Emit a reconciled InstanceIdentifier (OSD-IID) whose InstanceIdentifierData
//       is the fused subjects RANKED by combined score (primary = top), each a
//       candidate at the person layer. This is the "list with decreasing
//       accuracy" the IID is designed to carry.
//
//  Confidence of the reconciled primary reflects agreement: two modalities
//  agreeing on a subject sum to a high combined score; disagreement spreads the
//  mass and lowers the top - honest uncertainty, no arbitration by fiat.
// ---------------------------------------------------------------------------
public sealed class IdReconciliationAim
{
    private readonly double _faceWeight;   // w in [0,1]; voice weight = 1-w
    private const string TaxonomyUri = "https://schemas.mpai.community/taxonomies/person.json";

    public IdReconciliationAim(double faceWeight = 0.5)
    {
        if (faceWeight < 0 || faceWeight > 1) throw new ArgumentOutOfRangeException(nameof(faceWeight));
        _faceWeight = faceWeight;
    }

    public enum Rule { WeightedSum, Product }

    // Reconcile one person's face + voice evidence into a single OSD-IID.
    // Either vector may be empty (that modality absent / no match).
    // Fuse two OSD-IIDs (the mirror of Reconcile for the AIF wiring): FIR emits an
    // OSD-IID, SIR emits an OSD-IID, and IDR reconciles the two. Each IID is a
    // ranked candidate list with confidences - i.e. a score vector already - so we
    // read each candidate's InstanceLabel + LabelConfidenceLevel as a SubjectScore
    // and reuse the same normalise-and-fuse path. The coarse fallback candidates
    // ("face"/"speech", which are layer markers rather than subjects) are dropped:
    // they carry no subject identity to fuse. If a modality contributed only its
    // coarse marker (nobody matched), its vector is empty and fusion degrades to
    // the other modality, exactly as with empty score vectors.
    public InstanceIdentifier ReconcileIdentifiers(
        InstanceIdentifier? faceIdentity,
        InstanceIdentifier? voiceIdentity,
        Rule rule = Rule.WeightedSum,
        string? objectId = null,
        string? mInstanceID = null)
    {
        var faceScores  = ToScores(faceIdentity,  "person");
        var voiceScores = ToScores(voiceIdentity, "speaker");
        return Reconcile(faceScores, voiceScores, rule, objectId, mInstanceID);
    }

    // A candidate counts as a subject when its taxonomy reaches the identity layer
    // (person/speaker); coarser candidates (just "face"/"speech") are layer markers,
    // not subjects, and are skipped.
    private static List<SubjectScore> ToScores(InstanceIdentifier? iid, string identityLayer)
    {
        var scores = new List<SubjectScore>();
        if (iid is null) return scores;
        foreach (var c in iid.InstanceIdentifierData)
        {
            var levels = c.Taxonomy?.TaxonomyLevelIDs;
            bool isSubject = levels is not null && levels.Count > 0 &&
                             levels[levels.Count - 1] == identityLayer;
            if (isSubject && !string.IsNullOrWhiteSpace(c.InstanceLabel))
                scores.Add(new SubjectScore(c.InstanceLabel, (float)c.LabelConfidenceLevel));
        }
        return scores;
    }

    public InstanceIdentifier Reconcile(
        IReadOnlyList<SubjectScore> faceScores,
        IReadOnlyList<SubjectScore> voiceScores,
        Rule rule = Rule.WeightedSum,
        string? objectId = null,
        string? mInstanceID = null)
    {
        var face = Normalise(faceScores);
        var voice = Normalise(voiceScores);

        var subjects = new HashSet<string>(face.Keys);
        subjects.UnionWith(voice.Keys);

        var fused = new List<(string subject, double score)>();
        foreach (var subj in subjects)
        {
            bool hasF = face.TryGetValue(subj, out double f);
            bool hasV = voice.TryGetValue(subj, out double v);

            double combined = rule switch
            {
                // Product (naive-Bayes independence): only when BOTH present.
                Rule.Product when hasF && hasV => f * v,
                Rule.Product => hasF ? f : v,   // one modality -> pass through
                // Weighted sum over whichever modalities are present.
                _ => (hasF ? _faceWeight * f : 0) + (hasV ? (1 - _faceWeight) * v : 0)
            };
            fused.Add((subj, combined));
        }

        var ranked = fused.OrderByDescending(x => x.score).ToList();

        var candidates = ranked.Select(x => new InstanceCandidate
        {
            InstanceLabel = x.subject,
            LabelConfidenceLevel = Math.Clamp(x.score, 0.0, 1.0),
            Taxonomy = new InstanceTaxonomy
            {
                TaxonomyLevelIDs = new List<string> { "person" },
                TaxonomyDataURI = TaxonomyUri
            },
            TaxonomyConfidenceLevel = 1.0
        }).ToList();

        // Nothing to reconcile (both modalities empty) -> a coarse "person" IID.
        if (candidates.Count == 0)
        {
            candidates.Add(new InstanceCandidate
            {
                InstanceLabel = "person",
                LabelConfidenceLevel = 1.0,
                Taxonomy = new InstanceTaxonomy
                {
                    TaxonomyLevelIDs = new List<string> { "person" },
                    TaxonomyDataURI = TaxonomyUri
                },
                TaxonomyConfidenceLevel = 1.0
            });
        }

        return new InstanceIdentifier
        {
            MInstanceID = mInstanceID ?? "",
            InstanceIdentifier_ = Guid.NewGuid().ToString(),
            ObjectID = objectId,
            InstanceIdentifierData = candidates
        };
    }

    // Min-max normalise a score vector into [0,1]. If all equal (or single), map
    // to 1.0 (present with full within-modality confidence). Empty -> empty.
    private static Dictionary<string, double> Normalise(IReadOnlyList<SubjectScore> scores)
    {
        var map = new Dictionary<string, double>();
        if (scores.Count == 0) return map;
        float min = scores.Min(s => s.Score), max = scores.Max(s => s.Score);
        double range = max - min;
        foreach (var s in scores)
            map[s.SubjectId] = range > 1e-9 ? (s.Score - min) / range : 1.0;
        return map;
    }
}
