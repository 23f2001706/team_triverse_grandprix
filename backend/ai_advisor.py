from huggingface_hub import InferenceClient
from typing import List
from models import BottleneckAlert, ReroutesuGgestion

class AIAdvisor:
    """
    Uses HuggingFace Inference API with a text generation model
    to produce a human-readable safety advisory report based on
    simulation results.
    
    Model: mistralai/Mistral-7B-Instruct-v0.3 on HuggingFace Hub
    This is a capable instruction-tuned LLM suitable for 
    structured safety report generation.
    """
    
    # HuggingFace model - using a public inference endpoint
    MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"
    
    def __init__(self, hf_token: str = None):
        self.client = InferenceClient(
            model=self.MODEL_ID,
            token=hf_token
        )

    def _build_prompt(
        self,
        venue_name: str,
        crowd_size: int,
        bottlenecks: List[BottleneckAlert],
        suggestions: List[ReroutesuGgestion],
        risk_score: float,
        peak_time_minutes: float
    ) -> str:
        
        bottleneck_summary = "\n".join([
            f"- {b.node_name}: {b.severity.upper()} severity, "
            f"{b.occupancy_percent}% full, "
            f"~{b.estimated_wait_minutes} min wait"
            for b in bottlenecks[:5]  # Limit to top 5
        ]) if bottlenecks else "None detected"
        
        reroute_summary = "\n".join([
            f"- Reroute from {s.from_node} to {s.to_node}: {s.reason}"
            for s in suggestions[:3]
        ]) if suggestions else "No rerouting required"
        
        prompt = f"""<s>[INST] You are a crowd safety expert. 
Analyse the following crowd simulation results for {venue_name} and provide:
1. A brief overall safety assessment (2-3 sentences)
2. The top 3 immediate actions venue staff should take
3. One preventative recommendation for future events

SIMULATION DATA:
- Venue: {venue_name}
- Total crowd: {crowd_size} people
- Overall risk score: {risk_score}/100
- Peak congestion at: {peak_time_minutes:.1f} minutes into event

BOTTLENECKS DETECTED:
{bottleneck_summary}

REROUTING SUGGESTIONS:
{reroute_summary}

Keep your response concise, practical, and actionable. Format with clear headings. [/INST]"""
        
        return prompt

    def generate_safety_report(
        self,
        venue_name: str,
        crowd_size: int,
        bottlenecks: List[BottleneckAlert],
        suggestions: List[ReroutesuGgestion],
        risk_score: float,
        peak_time_seconds: int,
        time_step_seconds: int = 30
    ) -> str:
        """
        Generate AI safety advisory using HuggingFace LLM.
        Falls back to rule-based report if API unavailable.
        """
        peak_time_minutes = (peak_time_seconds * time_step_seconds) / 60
        
        prompt = self._build_prompt(
            venue_name=venue_name,
            crowd_size=crowd_size,
            bottlenecks=bottlenecks,
            suggestions=suggestions,
            risk_score=risk_score,
            peak_time_minutes=peak_time_minutes
        )
        
        try:
            response = self.client.text_generation(
                prompt,
                max_new_tokens=512,
                temperature=0.3,        # Lower = more factual
                repetition_penalty=1.1,
                do_sample=True
            )
            return response.strip()
            
        except Exception as e:
            print(f"HuggingFace API error: {e}")
            return self._fallback_report(
                venue_name, crowd_size, bottlenecks,
                suggestions, risk_score, peak_time_minutes
            )

    def _fallback_report(
        self,
        venue_name: str,
        crowd_size: int,
        bottlenecks: List[BottleneckAlert],
        suggestions: List[ReroutesuGgestion],
        risk_score: float,
        peak_time_minutes: float
    ) -> str:
        """Rule-based fallback when AI API is unavailable."""
        
        if risk_score >= 70:
            assessment = (
                f"⚠️ HIGH RISK: {venue_name} is experiencing severe congestion "
                f"with a risk score of {risk_score}/100. "
                "Immediate intervention is required to prevent crowd safety incidents."
            )
        elif risk_score >= 40:
            assessment = (
                f"⚡ MODERATE RISK: {venue_name} shows concerning congestion patterns "
                f"(risk score: {risk_score}/100). "
                "Proactive measures should be taken now."
            )
        else:
            assessment = (
                f"✅ LOW RISK: {venue_name} crowd flow is manageable "
                f"(risk score: {risk_score}/100). "
                "Continue monitoring as a precaution."
            )
        
        actions = []
        critical = [b for b in bottlenecks if b.severity == "critical"]
        high = [b for b in bottlenecks if b.severity == "high"]
        
        if critical:
            actions.append(
                f"1. IMMEDIATELY deploy staff to: "
                f"{', '.join(b.node_name for b in critical[:3])}"
            )
        if high:
            actions.append(
                f"2. Open additional access points near: "
                f"{', '.join(b.node_name for b in high[:3])}"
            )
        if suggestions:
            actions.append(
                f"3. Activate digital signage for alternate routes at "
                f"{len(suggestions)} locations"
            )
        if not actions:
            actions.append("1. Maintain current staffing levels")
            actions.append("2. Continue regular monitoring")
            actions.append("3. Keep emergency exits clear")
        
        report = f"""## 📊 Crowd Safety Report — {venue_name}

### Overall Assessment
{assessment}

**Peak congestion occurs at:** {peak_time_minutes:.1f} minutes into the event
**Total crowd:** {crowd_size:,} people | **Risk Score:** {risk_score}/100

### 🚨 Immediate Actions Required
{chr(10).join(actions)}

### 🔮 Preventative Recommendation
Consider implementing timed entry tickets or staggered admission 
to reduce the arrival surge. The simulation shows peak congestion 
at {peak_time_minutes:.0f} minutes — pre-event communication directing 
people to less congested gates can reduce this by up to 40%.

### 📍 Bottleneck Summary
"""
        for b in bottlenecks[:5]:
            emoji = {"critical": "🔴", "high": "🟠", 
                    "medium": "🟡", "low": "🟢"}.get(b.severity, "⚪")
            report += (
                f"{emoji} **{b.node_name}**: {b.severity.capitalize()} — "
                f"{b.occupancy_percent}% capacity, "
                f"~{b.estimated_wait_minutes} min wait\n"
            )
        
        return report
