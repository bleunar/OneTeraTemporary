// Professional Heatmap functionality for 1TERA
class HeatmapManager {
    constructor() {
        this.map = null;
        this.markers = [];
        this.heatmapLayer = null;
        this.clusterLayer = null;
        this.currentFilter = 'all';
        this.showHeatmap = false;
        this.showMarkers = true;
        this.showClusters = false;
        this.heatmapIntensity = 5;
    }

    init(mapElementId, initialData = []) {
        // Initialize map centered on Tigbauan, Iloilo
        this.map = L.map(mapElementId).setView([10.6747, 122.3964], 13);
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);
        
        // Add scale control
        L.control.scale({ imperial: false }).addTo(this.map);
        
        this.heatmapData = initialData;
        this.setupEventHandlers();
        this.updateLayers();
        this.updateStatistics();
        this.renderEmergencyList();
        this.addUserLocation();
    }

    setupEventHandlers() {
        // Filter handlers
        const filters = document.querySelectorAll('.heatmap-filter');
        filters.forEach(filter => {
            filter.addEventListener('click', () => {
                filters.forEach(f => f.classList.remove('active'));
                filter.classList.add('active');
                
                this.currentFilter = filter.getAttribute('data-filter');
                this.updateLayers();
                this.renderEmergencyList();
                this.updateStatistics();
            });
        });
        
        // Action button handlers
        document.getElementById('toggleHeatmapBtn').addEventListener('click', () => {
            this.showHeatmap = !this.showHeatmap;
            document.getElementById('toggleHeatmapBtn').classList.toggle('active', this.showHeatmap);
            this.updateLayers();
        });
        
        document.getElementById('toggleMarkersBtn').addEventListener('click', () => {
            this.showMarkers = !this.showMarkers;
            document.getElementById('toggleMarkersBtn').classList.toggle('active', this.showMarkers);
            this.updateLayers();
        });
        
        document.getElementById('toggleClustersBtn').addEventListener('click', () => {
            this.showClusters = !this.showClusters;
            document.getElementById('toggleClustersBtn').classList.toggle('active', this.showClusters);
            this.updateLayers();
        });
        
        // Heatmap intensity control
        const intensityControl = document.getElementById('heatmapIntensity');
        const intensityValue = document.getElementById('intensityValue');
        
        intensityControl.addEventListener('input', () => {
            this.heatmapIntensity = parseInt(intensityControl.value);
            const intensityLabels = ['Very Low', 'Low', 'Medium', 'High', 'Very High'];
            intensityValue.textContent = intensityLabels[Math.floor(this.heatmapIntensity / 2)] || 'Danger';
            this.updateLayers();
        });
    }

    updateLayers() {
        this.addHeatmapLayer();
        this.addClusterMarkers();
        this.addIndividualMarkers();
    }

    addHeatmapLayer() {
        // Remove existing heatmap layer
        if (this.heatmapLayer) {
            this.map.removeLayer(this.heatmapLayer);
        }
        
        const filteredData = this.getFilteredData();
        const heatmapPoints = filteredData
            .filter(report => report.lat && report.lng)
            .map(report => [report.lat, report.lng, 1]);
        
        // Calculate intensity based on slider
        const radius = 15 + (this.heatmapIntensity * 2);
        const blur = 10 + (this.heatmapIntensity * 1);
        
        if (heatmapPoints.length > 0) {
            this.heatmapLayer = L.heatLayer(heatmapPoints, {
                radius: radius,
                blur: blur,
                maxZoom: 17,
                gradient: {
                    0.2: 'blue',
                    0.4: 'cyan',
                    0.6: 'lime',
                    0.8: 'yellow',
                    1.0: 'red'
                },
                minOpacity: 0.3
            });
            
            if (this.showHeatmap) {
                this.heatmapLayer.addTo(this.map);
            }
        }
    }

    addClusterMarkers() {
        // Remove existing cluster layer
        if (this.clusterLayer) {
            this.map.removeLayer(this.clusterLayer);
        }
        
        const filteredData = this.getFilteredData();
        
        // Create marker cluster group
        this.clusterLayer = L.markerClusterGroup({
            chunkedLoading: true,
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: true,
            zoomToBoundsOnClick: true,
            iconCreateFunction: function (cluster) {
                const count = cluster.getChildCount();
                let size = 'small';
                
                if (count > 10) size = 'large';
                else if (count > 5) size = 'medium';
                
                return L.divIcon({
                    html: '<div><span>' + count + '</span></div>',
                    className: 'marker-cluster marker-cluster-' + size,
                    iconSize: L.point(40, 40)
                });
            }
        });
        
        filteredData.forEach(report => {
            if (report.lat && report.lng) {
                const marker = this.createMarker(report);
                this.clusterLayer.addLayer(marker);
            }
        });
        
        if (this.showClusters && filteredData.length > 0) {
            this.map.addLayer(this.clusterLayer);
        }
    }

    addIndividualMarkers() {
        // Clear existing markers
        this.markers.forEach(marker => this.map.removeLayer(marker));
        this.markers = [];
        
        if (!this.showMarkers) return;
        
        const filteredData = this.getFilteredData();
        
        filteredData.forEach(report => {
            if (report.lat && report.lng) {
                const marker = this.createMarker(report);
                marker.addTo(this.map);
                this.markers.push(marker);
            }
        });
    }

    createMarker(report) {
        const isMyReport = report.ownership === 'my_report';
        const style = emergencyColors[report.type] || emergencyColors.other;
        const icon = emergencyIcons[report.type] || 'circle-exclamation';
        
        // Create custom icon
        const markerIcon = L.divIcon({
            className: `emergency-marker ${isMyReport ? 'my-report' : ''}`,
            html: `
                <div style="
                    background-color: ${style};
                    width: ${isMyReport ? '24px' : '20px'};
                    height: ${isMyReport ? '24px' : '20px'};
                    border: 3px solid white;
                    border-radius: 50%;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-size: ${isMyReport ? '12px' : '10px'};
                    font-weight: bold;
                    ${isMyReport ? 'border: 3px solid #1d4ed8; box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.3);' : ''}
                ">
                    <i class="fas fa-${icon}"></i>
                </div>
            `,
            iconSize: isMyReport ? [30, 30] : [26, 26],
            iconAnchor: isMyReport ? [15, 15] : [13, 13]
        });
        
        const marker = L.marker([report.lat, report.lng], { icon: markerIcon })
            .bindPopup(this.createPopupContent(report));
        
        return marker;
    }

    createPopupContent(report) {
        const isMyReport = report.ownership === 'my_report';
        const statusClass = `status-${report.status.replace('_', '')}`;
        const statusText = report.status.replace('_', ' ').toUpperCase();
        const timeAgo = this.getTimeAgo(report.time);
        const ownershipBadge = isMyReport ? 
            '<span class="ownership-badge ownership-my"><i class="fas fa-user"></i> My Report</span>' :
            '<span class="ownership-badge ownership-other"><i class="fas fa-users"></i> Other User</span>';
        
        return `
            <div class="marker-popup">
                <div class="popup-header">
                    <i class="fas fa-${emergencyIcons[report.type]}"></i>
                    ${report.type.toUpperCase()} EMERGENCY
                    ${ownershipBadge}
                </div>
                
                <div class="popup-meta">
                    <div><strong>Reported by:</strong> ${report.user_name || 'Anonymous'}</div>
                    <div><strong>Time:</strong> ${report.time} (${timeAgo})</div>
                    <div><strong>Location:</strong> ${report.location}</div>
                    <div><strong>Status:</strong> <span class="status-badge ${statusClass}">${statusText}</span></div>
                </div>
                
                ${report.description ? `
                    <div class="popup-description">
                        <strong>Description:</strong><br>
                        ${report.description}
                    </div>
                ` : ''}
                
                ${report.image ? `
                    <div style="margin-top: 10px;">
                        <img src="/static/uploads/${report.image}" 
                             alt="Emergency Image" 
                             class="popup-image"
                             onerror="this.style.display='none'">
                    </div>
                ` : ''}
            </div>
        `;
    }

    getFilteredData() {
        if (this.currentFilter === 'all') {
            return this.heatmapData;
        } else if (this.currentFilter === 'my_reports') {
            return this.heatmapData.filter(report => report.ownership === 'my_report');
        } else {
            return this.heatmapData.filter(report => report.type === this.currentFilter);
        }
    }

    getTimeAgo(timestamp) {
        const now = new Date();
        const reportTime = new Date(timestamp);
        const diffMs = now - reportTime;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }

    addUserLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const userLat = position.coords.latitude;
                    const userLng = position.coords.longitude;
                    
                    // Add user location marker
                    const userIcon = L.divIcon({
                        className: 'user-location-marker',
                        html: `
                            <div style="
                                background-color: #2563eb;
                                width: 16px;
                                height: 16px;
                                border: 3px solid white;
                                border-radius: 50%;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                                animation: pulse 2s infinite;
                            "></div>
                        `,
                        iconSize: [22, 22],
                        iconAnchor: [11, 11]
                    });
                    
                    L.marker([userLat, userLng], { icon: userIcon })
                        .addTo(this.map)
                        .bindPopup('<strong>Your Current Location</strong><br>You are here')
                        .openPopup();
                },
                (error) => {
                    console.log('Geolocation error:', error);
                }
            );
        }
    }

    updateStatistics() {
        const total = this.heatmapData.length;
        const myReports = this.heatmapData.filter(r => r.ownership === 'my_report').length;
        const active = this.heatmapData.filter(r => r.status !== 'resolved').length;
        const resolved = this.heatmapData.filter(r => r.status === 'resolved').length;
        
        document.getElementById('totalEmergencies').textContent = total;
        document.getElementById('myReports').textContent = myReports;
        document.getElementById('activeEmergencies').textContent = active;
        document.getElementById('resolvedEmergencies').textContent = resolved;
    }

    renderEmergencyList() {
        const emergenciesList = document.getElementById('emergenciesList');
        const filteredData = this.getFilteredData().slice(0, 15); // Show latest 15
        
        if (filteredData.length > 0) {
            emergenciesList.innerHTML = filteredData.map(report => {
                const isMyReport = report.ownership === 'my_report';
                const statusClass = `status-${report.status.replace('_', '')}`;
                
                return `
                    <div class="report-item ${isMyReport ? 'my-report' : ''}">
                        <div class="report-icon" style="background-color: ${emergencyColors[report.type]}20; color: ${emergencyColors[report.type]}">
                            <i class="fas fa-${emergencyIcons[report.type]}"></i>
                        </div>
                        <div class="report-details">
                            <div class="report-title">
                                ${report.type.charAt(0).toUpperCase() + report.type.slice(1)} Emergency
                                <span class="report-status ${statusClass}">
                                    ${report.status.replace('_', ' ').toUpperCase()}
                                </span>
                                ${isMyReport ? 
                                    '<span class="ownership-badge ownership-my"><i class="fas fa-user"></i> My Report</span>' :
                                    '<span class="ownership-badge ownership-other"><i class="fas fa-users"></i> Other</span>'
                                }
                            </div>
                            <div class="report-meta">
                                ${report.location} • ${report.time} • Reported by: ${report.user_name || 'Anonymous'}
                            </div>
                            ${report.description ? `
                                <div class="report-description">
                                    ${report.description}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            emergenciesList.innerHTML = `
                <div class="text-center" style="padding: 2rem;">
                    <i class="fas fa-map-marker-alt" style="font-size: 3rem; color: #6b7280; margin-bottom: 1rem;"></i>
                    <p>No emergency reports available for selected filter</p>
                </div>
            `;
        }
    }

    updateData(newData) {
        this.heatmapData = newData;
        this.updateLayers();
        this.updateStatistics();
        this.renderEmergencyList();
    }
}

// Initialize heatmap when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('heatmap')) {
        const heatmapManager = new HeatmapManager();
        heatmapManager.init('heatmap', heatmapData);
        
        // Make heatmapManager available globally for updates
        window.heatmapManager = heatmapManager;
        
        // Auto-refresh data every 30 seconds
        setInterval(() => {
            // In a real application, you would fetch new data from the server
            // For now, we'll just use the initial data
            console.log('Heatmap data refresh triggered');
        }, 30000);
    }
});