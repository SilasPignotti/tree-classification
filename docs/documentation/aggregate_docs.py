#!/usr/bin/env python3
"""
Aggregates markdown files from documentation subdirectories into gpt_knowledge files.
This script combines multiple markdown files in a logical order into single consolidated files.
"""

from pathlib import Path
import re


def aggregate_documents(source_dir, target_file, section_order=None):
    """
    Aggregate markdown files from source directory into a single target file.
    
    Args:
        source_dir: Path to source documentation directory
        target_file: Path to target aggregated file
        section_order: Optional list of filenames in desired order
    """
    source_path = Path(source_dir)
    target_path = Path(target_file)
    
    if not source_path.exists():
        print(f"❌ Source directory not found: {source_path}")
        return False
    
    # Get all markdown files
    md_files = sorted(source_path.glob("*.md"))
    
    if not md_files:
        print(f"❌ No markdown files found in {source_path}")
        return False
    
    # Optionally reorder files
    if section_order:
        ordered_files = []
        for filename in section_order:
            for md_file in md_files:
                if md_file.name == filename:
                    ordered_files.append(md_file)
                    break
        # Add any files not in the order list
        for md_file in md_files:
            if md_file not in ordered_files:
                ordered_files.append(md_file)
        md_files = ordered_files
    
    print(f"📄 Aggregating {len(md_files)} files from {source_path.name}")
    
    # Read and aggregate files
    aggregated_content = []
    
    for i, md_file in enumerate(md_files, 1):
        print(f"  {i}. {md_file.name}")
        
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Add separator between files (except before first file)
        if i > 1:
            aggregated_content.append("\n\n" + "---\n\n")
        
        aggregated_content.append(content)
    
    # Write to target file
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(target_path, "w", encoding="utf-8") as f:
        f.write("".join(aggregated_content))
    
    file_size_mb = target_path.stat().st_size / (1024 * 1024)
    print(f"✅ Successfully created: {target_path} ({file_size_mb:.1f} MB)\n")
    
    return True


def main():
    """Main execution function."""
    base_docs = Path("/Users/silas/Documents/projects/uni/Geo Projektarbeit/project/docs")
    
    # Configuration for aggregation
    configs = [
        {
            "name": "00_Projektdesign_und_Methodik",
            "source": base_docs / "documentation" / "00_Projektdesign_und_Methodik",
            "target": base_docs / "gpt_knowledge" / "00_Projektdesign_und_Methodik.md",
            "order": [
                "01_Projektübersicht.md",
                "02_Methodische_Grundlagen.md",
                "03_Datapipeline_Architektur.md"
            ]
        },
        {
            "name": "01_Data_Processing",
            "source": base_docs / "documentation" / "01_Data_Processing",
            "target": base_docs / "gpt_knowledge" / "01_Data_Processing.md",
            "order": [
                "01_Stadtgrenzen_Methodik.md",
                "02_Baumkataster_Methodik.md",
                "03_Hoehendaten_DOM_DGM_Methodik.md",
                "04_CHM_Erstellung_Methodik.md",
                "05_CHM_Resampling_Methodik.md",
                "06_Sentinel2_Verarbeitung_Methodik.md",
                "07_Baumkorrektur_Methodik.md"
            ]
        },
        {
            "name": "02_Feature_Engineering",
            "source": base_docs / "documentation" / "02_Feature_Engineering",
            "target": base_docs / "gpt_knowledge" / "02_Feature_Engineering.md",
            "order": [
                "01_Feature_Extraction_Methodik.md",
                "02_Data_Quality_Control_Methodik.md",
                "03_Temporal_Feature_Selection_JM_Methodik.md",
                "04_NaN_Handling_Plausibility_Methodik.md",
                "05_CHM_Relevance_Assessment_Methodik.md",
                "06_Correlation_Analysis_Redundancy_Reduction_Methodik.md",
                "07_Outlier_Detection_Final_Filtering_Methodik.md",
                "08_Spatial_Splits_Stratification_Methodik.md"
            ]
        },
        {
            "name": "03_Experiments",
            "source": base_docs / "documentation" / "03_Experiments",
            "target": base_docs / "gpt_knowledge" / "03_Experiments.md",
            "order": [
                "00_Experiment_Design.md",
                "01_Phase_0_Methodik.md"
            ]
        }
    ]
    
    print("🚀 Starting documentation aggregation...\n")
    
    results = []
    for config in configs:
        if config["source"].exists():
            success = aggregate_documents(
                config["source"],
                config["target"],
                config["order"]
            )
            results.append((config["name"], success))
        else:
            print(f"⏭️  Skipping {config['name']} (source directory not found)\n")
            results.append((config["name"], None))
    
    # Summary
    print("=" * 60)
    print("📊 AGGREGATION SUMMARY")
    print("=" * 60)
    for name, success in results:
        if success is None:
            status = "⏭️  SKIPPED"
        elif success:
            status = "✅ SUCCESS"
        else:
            status = "❌ FAILED"
        print(f"{status}: {name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
