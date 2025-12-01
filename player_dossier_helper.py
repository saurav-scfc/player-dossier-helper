import streamlit as st
from swancode.statsbomb import get_statsbomb_data
import pandas as pd
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="Player Dossier Generator",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# StatsBomb credentials
SB_USER = 'sauravsharma@swanseacity.com'
SB_PWD = 'FWGTktT6'

# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

@st.cache_data(show_spinner=False)
def load_competitions():
    """Load all available competitions from StatsBomb"""
    comps = get_statsbomb_data.get_process_statsbomb_competitions(
        sb_user=SB_USER, sb_pwd=SB_PWD
    )
    return comps


def load_players_for_competition_seasons(comps, competition_name, seasons):
    """Load all players who made crosses in selected competition and seasons"""
    # Filter competition data
    comp_data = comps[comps['competition_name'] == competition_name]
    selected_season_data = comp_data[comp_data['season_name'].isin(seasons)]

    all_players = set()

    for _, season in selected_season_data.iterrows():
        try:
            # Get matches for this season
            matches, _ = get_statsbomb_data.get_process_statsbomb_matches_and_managers(
                season, sb_user=SB_USER, sb_pwd=SB_PWD
            )

            # Sample first 10 matches to get player list (for performance)
            sample_matches = matches.head(10)

            # Get events
            events, _, _ = get_statsbomb_data.get_process_statsbomb_events(
                sample_matches, sb_user=SB_USER, sb_pwd=SB_PWD
            )

            # Get unique players who made crosses
            cross_players = events[
                (events['type_name'] == 'Pass') & (events['cross'] == True)
            ]['player_name'].unique()
            all_players.update(cross_players)
        except Exception as e:
            st.warning(f"Could not load data for season {season['season_name']}: {str(e)}")
            continue

    return sorted(list(all_players))


def load_event_data_for_player(player_name, competition_name, seasons, comps):
    """Load all event data for a specific player across selected seasons"""
    # Filter competition data
    comp_data = comps[comps['competition_name'] == competition_name]
    selected_season_data = comp_data[comp_data['season_name'].isin(seasons)]

    all_season_matches = []
    all_season_events_list = []

    for _, season in selected_season_data.iterrows():
        try:
            # Get matches
            matches, _ = get_statsbomb_data.get_process_statsbomb_matches_and_managers(
                season, sb_user=SB_USER, sb_pwd=SB_PWD
            )

            # Get events
            events, _, _ = get_statsbomb_data.get_process_statsbomb_events(
                matches, sb_user=SB_USER, sb_pwd=SB_PWD
            )

            all_season_matches.append(matches)
            all_season_events_list.append(events)
        except Exception as e:
            st.error(f"Error loading data for {season['season_name']}: {str(e)}")
            continue

    # Combine all data
    if all_season_matches and all_season_events_list:
        all_matches = pd.concat(all_season_matches, ignore_index=True)
        all_events = pd.concat(all_season_events_list, ignore_index=True)
        return all_events, all_matches
    else:
        return pd.DataFrame(), pd.DataFrame()


# ============================================================================
# MAP GENERATION FUNCTIONS
# ============================================================================

def generate_crossing_map(player_name, events_df, matches_df, seasons):
    """Generate crossing map visualization using Plotly"""

    # Filter for crosses by the specified player
    player_crosses = events_df[
        (events_df['type_name'] == 'Pass') &
        (events_df['cross'] == True) &
        (events_df['player_name'].str.contains(player_name, case=False, na=False))
    ].copy()

    # Normalize coordinates so attack is always upwards
    player_crosses['x_norm'] = player_crosses.apply(
        lambda row: row['x'] if pd.notna(row.get('team_name')) else row['x'],
        axis=1
    )
    player_crosses['y_norm'] = player_crosses.apply(
        lambda row: row['y'] if pd.notna(row.get('team_name')) else row['y'],
        axis=1
    )

    # Normalize end coordinates
    player_crosses['end_x_norm'] = player_crosses.apply(
        lambda row: row['end_x'] if pd.notna(row.get('end_x')) else row['x'],
        axis=1
    )
    player_crosses['end_y_norm'] = player_crosses.apply(
        lambda row: row['end_y'] if pd.notna(row.get('end_y')) else row['y'],
        axis=1
    )

    # Create a dictionary to map match_id to match details
    match_details = {}
    for _, match in matches_df.iterrows():
        match_details[match['match_id']] = {
            'home_team': match['home_team_name'],
            'away_team': match['away_team_name'],
            'match_date': match.get('match_date', '')
        }

    # Create hover text for each cross
    hover_texts = []
    for idx, cross in player_crosses.iterrows():
        match_id = cross.get('match_id')
        minute = cross.get('minute', 0)
        second = int(cross.get('second', 0)) if pd.notna(cross.get('second')) else 0

        # Get match details
        match_info = match_details.get(match_id, {})
        home_team = match_info.get('home_team', 'Unknown')
        away_team = match_info.get('away_team', 'Unknown')

        # Get body part used
        body_part = cross.get('body_part_name', 'Unknown')

        # Check if cross was successful
        outcome = cross.get('outcome_name')
        if pd.isna(outcome) or outcome == '':
            success = 'Successful'
        else:
            success = f'Unsuccessful ({outcome})'

        # Create hover text
        hover_text = f"{home_team} vs {away_team}<br>Time: {minute}:{second:02d}<br>Body part: {body_part}<br>Status: {success}"
        hover_texts.append(hover_text)

    player_crosses['hover_text'] = hover_texts

    # Create interactive pitch using Plotly
    fig = go.Figure()

    # Draw pitch outline
    fig.add_trace(go.Scatter(
        x=[0, 0, 80, 80, 0], y=[0, 120, 120, 0, 0],
        mode='lines', line=dict(color='black', width=2),
        showlegend=False, hoverinfo='skip'
    ))

    # Draw halfway line
    fig.add_trace(go.Scatter(
        x=[0, 80], y=[60, 60],
        mode='lines', line=dict(color='black', width=2),
        showlegend=False, hoverinfo='skip'
    ))

    # Draw center circle
    fig.add_shape(
        type='circle', x0=30.85, y0=50.85, x1=49.15, y1=69.15,
        line=dict(color='black', width=2), fillcolor='rgba(0,0,0,0)'
    )

    # Draw center spot
    fig.add_trace(go.Scatter(
        x=[40], y=[60], mode='markers',
        marker=dict(color='black', size=3),
        showlegend=False, hoverinfo='skip'
    ))

    # Draw penalty boxes
    fig.add_trace(go.Scatter(
        x=[18, 18, 62, 62, 18], y=[0, 18, 18, 0, 0],
        mode='lines', line=dict(color='black', width=2),
        showlegend=False, hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=[18, 18, 62, 62, 18], y=[102, 120, 120, 102, 102],
        mode='lines', line=dict(color='black', width=2),
        showlegend=False, hoverinfo='skip'
    ))

    # Draw six-yard boxes
    fig.add_trace(go.Scatter(
        x=[30, 30, 50, 50, 30], y=[0, 6, 6, 0, 0],
        mode='lines', line=dict(color='black', width=2),
        showlegend=False, hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=[30, 30, 50, 50, 30], y=[114, 120, 120, 114, 114],
        mode='lines', line=dict(color='black', width=2),
        showlegend=False, hoverinfo='skip'
    ))

    # Filter crosses to only include those made with feet
    player_crosses_feet = player_crosses[
        player_crosses['body_part_name'].isin(['Left Foot', 'Right Foot'])
    ].copy()

    # Draw trajectory arrows for each cross
    for idx, cross in player_crosses_feet.iterrows():
        is_successful = pd.isna(cross.get('outcome_name'))
        arrow_color = 'green' if is_successful else 'red'
        arrow_width = 2 if is_successful else 1

        fig.add_annotation(
            x=cross['end_y_norm'],
            y=cross['end_x_norm'],
            ax=cross['y_norm'],
            ay=cross['x_norm'],
            xref='x', yref='y',
            axref='x', ayref='y',
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=arrow_width,
            arrowcolor=arrow_color,
            opacity=0.6
        )

    # Separate crosses by foot and success
    left_foot_successful = player_crosses_feet[
        (player_crosses_feet['body_part_name'] == 'Left Foot') &
        (player_crosses_feet['outcome_name'].isna())
    ]
    left_foot_unsuccessful = player_crosses_feet[
        (player_crosses_feet['body_part_name'] == 'Left Foot') &
        (player_crosses_feet['outcome_name'].notna())
    ]
    right_foot_successful = player_crosses_feet[
        (player_crosses_feet['body_part_name'] == 'Right Foot') &
        (player_crosses_feet['outcome_name'].isna())
    ]
    right_foot_unsuccessful = player_crosses_feet[
        (player_crosses_feet['body_part_name'] == 'Right Foot') &
        (player_crosses_feet['outcome_name'].notna())
    ]

    # Plot markers
    if len(left_foot_successful) > 0:
        fig.add_trace(go.Scatter(
            x=left_foot_successful['y_norm'],
            y=left_foot_successful['x_norm'],
            mode='markers',
            marker=dict(color='green', size=12, symbol='triangle-up',
                       line=dict(color='black', width=1.5), opacity=0.7),
            text=left_foot_successful['hover_text'],
            hoverinfo='text',
            name='Left Foot Successful'
        ))

    if len(left_foot_unsuccessful) > 0:
        fig.add_trace(go.Scatter(
            x=left_foot_unsuccessful['y_norm'],
            y=left_foot_unsuccessful['x_norm'],
            mode='markers',
            marker=dict(color='red', size=12, symbol='triangle-up',
                       line=dict(color='black', width=1.5), opacity=0.7),
            text=left_foot_unsuccessful['hover_text'],
            hoverinfo='text',
            name='Left Foot Unsuccessful'
        ))

    if len(right_foot_successful) > 0:
        fig.add_trace(go.Scatter(
            x=right_foot_successful['y_norm'],
            y=right_foot_successful['x_norm'],
            mode='markers',
            marker=dict(color='green', size=10,
                       line=dict(color='black', width=1.5), opacity=0.7),
            text=right_foot_successful['hover_text'],
            hoverinfo='text',
            name='Right Foot Successful'
        ))

    if len(right_foot_unsuccessful) > 0:
        fig.add_trace(go.Scatter(
            x=right_foot_unsuccessful['y_norm'],
            y=right_foot_unsuccessful['x_norm'],
            mode='markers',
            marker=dict(color='red', size=10,
                       line=dict(color='black', width=1.5), opacity=0.7),
            text=right_foot_unsuccessful['hover_text'],
            hoverinfo='text',
            name='Right Foot Unsuccessful'
        ))

    # Configure layout
    season_text = ', '.join(seasons)
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(range=[0, 80], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[0, 120], showgrid=False, zeroline=False, visible=False,
                  scaleanchor='x', scaleratio=1),
        width=1000,
        height=1200,
        showlegend=False,
        title=None,
        margin=dict(r=200, l=50, t=50, b=50)
    )

    # Add legend as annotation box
    total_games = len(matches_df) if not matches_df.empty else 0
    legend_text = (
        f"<b>Legend</b><br>"
        f"<b>Shape:</b><br>"
        f"● Circle = Right Foot<br>"
        f"▲ Triangle = Left Foot<br>"
        f"<br>"
        f"<b>Color:</b><br>"
        f"<span style='color:green;'>●</span> Green = Successful<br>"
        f"<span style='color:red;'>●</span> Red = Unsuccessful<br>"
        f"<br>"
        f"<b>Data Info:</b><br>"
        f"Season: {season_text}<br>"
        f"Games: {total_games}<br>"
        f"Total Crosses: {len(player_crosses_feet)}"
    )

    fig.add_annotation(
        x=1.02, y=0.98,
        xref='paper', yref='paper',
        text=legend_text,
        showarrow=False,
        align='left',
        bgcolor='rgba(255, 255, 255, 0.9)',
        bordercolor='black',
        borderwidth=2,
        font=dict(size=11, color='black'),
        xanchor='left',
        yanchor='top'
    )

    return fig


# ============================================================================
# PDF EXPORT FUNCTION
# ============================================================================

def generate_pdf_html(player_name, report_type, seasons, plotly_fig):
    """Generate clean HTML for PDF export"""

    # Convert Plotly figure to HTML div
    fig_html = plotly_fig.to_html(
        include_plotlyjs='cdn',
        div_id='map-viz',
        config={'displayModeBar': False}
    )

    seasons_text = ', '.join(seasons)

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{player_name} - {report_type}</title>
        <style>
            @page {{
                size: A4;
                margin: 0;
            }}
            body {{
                margin: 0;
                padding: 0;
                font-family: Arial, sans-serif;
                background: white;
            }}
            .header {{
                background: #1a1a1a;
                padding: 20px 40px;
                color: white;
            }}
            .header h3 {{
                margin: 0;
                font-size: 16px;
                font-weight: bold;
            }}
            .accent-bar {{
                background: #b87333;
                height: 8px;
            }}
            .content {{
                padding: 40px;
            }}
            .title {{
                text-align: center;
                color: #1a1a1a;
                margin: 20px 0 10px 0;
                font-size: 28px;
                font-weight: bold;
            }}
            .subtitle {{
                text-align: center;
                color: #666;
                margin-bottom: 30px;
                font-size: 18px;
            }}
            #map-viz {{
                width: 100%;
                min-height: 800px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h3>SWANSEA CITY AFC</h3>
        </div>
        <div class="accent-bar"></div>
        <div class="content">
            <h1 class="title">{report_type.upper()}</h1>
            <h2 class="subtitle">{player_name} | Season: {seasons_text}</h2>
            {fig_html}
        </div>
    </body>
    </html>
    """

    return html_template


# ============================================================================
# MAIN STREAMLIT APP
# ============================================================================

def main():
    # Initialize session state
    if 'generated_map' not in st.session_state:
        st.session_state.generated_map = None
    if 'player_name' not in st.session_state:
        st.session_state.player_name = None
    if 'report_type' not in st.session_state:
        st.session_state.report_type = None
    if 'seasons' not in st.session_state:
        st.session_state.seasons = []

    # SIDEBAR
    st.sidebar.title("⚽ Report Configuration")
    st.sidebar.markdown("---")

    # 1. Report Type Selection
    report_type = st.sidebar.selectbox(
        "📊 Report Type",
        ["Crossing Analysis", "Passing Analysis", "Shooting Analysis", "Carries Analysis"],
        help="Select the type of analysis you want to generate"
    )

    # 2. Competition Selection
    with st.spinner("Loading competitions..."):
        comps = load_competitions()

    competition_options = sorted(comps['competition_name'].unique().tolist())
    selected_competition = st.sidebar.selectbox(
        "🏆 Competition",
        competition_options,
        index=competition_options.index('Championship') if 'Championship' in competition_options else 0,
        help="Select the competition to analyze"
    )

    # 3. Season Selection (multi-select)
    comp_data = comps[comps['competition_name'] == selected_competition]
    available_seasons = sorted(comp_data['season_name'].unique().tolist(), reverse=True)
    selected_seasons = st.sidebar.multiselect(
        "📅 Seasons",
        available_seasons,
        default=[available_seasons[0]] if available_seasons else [],
        help="Select one or more seasons to analyze"
    )

    # 4. Player Selection
    selected_player = None
    if selected_seasons:
        with st.spinner("Loading players..."):
            player_list = load_players_for_competition_seasons(
                comps, selected_competition, selected_seasons
            )

        if player_list:
            selected_player = st.sidebar.selectbox(
                "👤 Player",
                player_list,
                help="Select the player to analyze"
            )
        else:
            st.sidebar.warning("No players found with cross data for selected seasons")
    else:
        st.sidebar.info("Please select at least one season to load players")

    st.sidebar.markdown("---")

    # 5. Generate Map Button
    generate_button = st.sidebar.button(
        "🎯 Generate Map",
        type="primary",
        use_container_width=True,
        disabled=not (selected_player and selected_seasons)
    )

    if generate_button and selected_player and selected_seasons:
        with st.spinner(f"Generating {report_type} for {selected_player}..."):
            # Load event data
            events_df, matches_df = load_event_data_for_player(
                selected_player, selected_competition, selected_seasons, comps
            )

            if events_df.empty or matches_df.empty:
                st.error("No data found for selected player and seasons")
            else:
                # Generate map based on report type
                if report_type == "Crossing Analysis":
                    fig = generate_crossing_map(selected_player, events_df, matches_df, selected_seasons)
                elif report_type == "Passing Analysis":
                    st.warning("Passing Analysis coming soon!")
                    fig = None
                elif report_type == "Shooting Analysis":
                    st.warning("Shooting Analysis coming soon!")
                    fig = None
                else:  # Carries Analysis
                    st.warning("Carries Analysis coming soon!")
                    fig = None

                # Store in session state
                if fig:
                    st.session_state.generated_map = fig
                    st.session_state.player_name = selected_player
                    st.session_state.report_type = report_type
                    st.session_state.seasons = selected_seasons
                    st.success("Map generated successfully!")

    # MAIN CONTENT
    st.title("🦢 Player Dossier Report Generator")
    st.markdown("### Swansea City AFC")

    if st.session_state.generated_map:
        # Template header
        st.markdown("""
        <div style="background: #1a1a1a; padding: 20px 40px; margin: 20px 0 0 0; border-radius: 8px 8px 0 0;">
            <div style="color: white; font-size: 16px; font-weight: bold;">SWANSEA CITY AFC</div>
        </div>
        <div style="background: #b87333; height: 6px; margin: 0;"></div>
        """, unsafe_allow_html=True)

        # Report title
        seasons_text = ', '.join(st.session_state.seasons)
        st.markdown(f"""
        <h2 style="text-align: center; color: #1a1a1a; margin-top: 30px; font-size: 32px;">
            {st.session_state.report_type.upper()}
        </h2>
        <h3 style="text-align: center; color: #666; margin-bottom: 40px; font-size: 20px;">
            {st.session_state.player_name} | Season: {seasons_text}
        </h3>
        """, unsafe_allow_html=True)

        # Display map
        st.plotly_chart(st.session_state.generated_map, use_container_width=True)

        # Download PDF button
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📥 Export")

        html_content = generate_pdf_html(
            st.session_state.player_name,
            st.session_state.report_type,
            st.session_state.seasons,
            st.session_state.generated_map
        )

        st.sidebar.download_button(
            label="Download HTML Report",
            data=html_content,
            file_name=f"{st.session_state.player_name.replace(' ', '_')}_{st.session_state.report_type.replace(' ', '_')}.html",
            mime="text/html",
            use_container_width=True
        )
        st.sidebar.caption("💡 Tip: Open HTML in browser and use Print to PDF for final report")

    else:
        # Instructions
        st.info("""
        ### 👋 Welcome to the Player Dossier Generator!

        **Get Started:**
        1. 📊 Select a report type from the sidebar (Crossing, Passing, Shooting, or Carries)
        2. 🏆 Choose a competition (e.g., Championship)
        3. 📅 Pick one or more seasons
        4. 👤 Select a player from the dropdown
        5. 🎯 Click "Generate Map" to create the visualization
        6. 📥 Download as HTML/PDF when ready

        The report will appear here with a live preview featuring the Swansea City AFC template.
        """)

        # Show example image or placeholder
        st.markdown("---")
        st.markdown("### 📋 Features")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**🎨 Professional Template**")
            st.caption("Clean design with Swansea City branding")
        with col2:
            st.markdown("**📊 Interactive Maps**")
            st.caption("Hover over data points for details")
        with col3:
            st.markdown("**📥 PDF Export**")
            st.caption("Download ready-to-share reports")


if __name__ == "__main__":
    main()
